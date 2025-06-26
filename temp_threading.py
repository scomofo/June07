# app/core/threading.py
import asyncio
import logging
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, List, Optional, Union
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QRunnable, QThreadPool
from dataclasses import dataclass
from datetime import datetime
import weakref

logger = logging.getLogger(__name__) # Module-level logger

@dataclass
class TaskResult:
    task_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class Worker(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal()
        error = pyqtSignal(Exception)
        result = pyqtSignal(object)
        progress = pyqtSignal(int)
        status = pyqtSignal(str)

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = self.Signals()
        self.is_cancelled = False

    def run(self):
        try:
            if self.is_cancelled:
                return
            result = self.fn(*self.args, **self.kwargs)
            if not self.is_cancelled:
                self.signals.result.emit(result)
        except Exception as e:
            logger.error(f"Worker error in function {getattr(self.fn, '__name__', 'unknown')}: {e}", exc_info=True)
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()

    def cancel(self):
        self.is_cancelled = True

class AsyncWorker(QThread):
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(Exception)
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    # 'finished' signal is inherited from QThread

    def __init__(self, async_fn: Callable, *args, **kwargs):
        super().__init__()
        self.async_fn = async_fn
        self.args = args
        self.kwargs = {k: v for k, v in kwargs.items() if k not in ['on_result', 'on_error', 'callback']}
        self.is_cancelled = False
        self._loop = None

    def run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            logger.debug(f"AsyncWorker: Event loop created and set for {getattr(self.async_fn, '__name__', 'unknown')}")
            result = self._loop.run_until_complete(
                self.async_fn(*self.args, **self.kwargs)
            )
            if not self.is_cancelled:
                self.result_ready.emit(result)
                logger.debug(f"AsyncWorker: Result emitted for {getattr(self.async_fn, '__name__', 'unknown')}")
        except Exception as e:
            logger.error(f"AsyncWorker error in task {getattr(self.async_fn, '__name__', 'unknown')}: {e}", exc_info=True)
            self.error_occurred.emit(e)
        finally:
            # QThread.finished is emitted automatically after run() returns.
            # The crucial part is robust loop cleanup BEFORE run() method exits.
            if self._loop:
                try:
                    logger.debug(f"AsyncWorker: Preparing to stop and close loop for {getattr(self.async_fn, '__name__', 'unknown')}")
                    if self._loop.is_running():
                        self._loop.call_soon_threadsafe(self._loop.stop)
                        self._loop.run_forever()
                        logger.debug(f"AsyncWorker: Loop stopped for {getattr(self.async_fn, '__name__', 'unknown')}")
                    else:
                        logger.debug(f"AsyncWorker: Loop for {getattr(self.async_fn, '__name__', 'unknown')} was already stopped.")
                except Exception as el_run_err:
                    logger.error(f"AsyncWorker: Error during loop final processing (run_forever/stop): {el_run_err}", exc_info=True)
                finally: # Ensure loop close is attempted
                    logger.debug(f"AsyncWorker: Closing loop for {getattr(self.async_fn, '__name__', 'unknown')}")
                    self._loop.close()
                    self._loop = None
                    logger.debug(f"AsyncWorker: Loop closed for {getattr(self.async_fn, '__name__', 'unknown')}")
            # The base QThread.finished signal will be emitted after this run() method completes.

    def cancel(self):
        self.is_cancelled = True
        logger.debug(f"AsyncWorker: Cancel called for {getattr(self.async_fn, '__name__', 'unknown')}")
        if self._loop and self._loop.is_running():
            logger.debug(f"AsyncWorker: Loop is running, attempting to cancel all tasks for {getattr(self.async_fn, '__name__', 'unknown')}")
            for task_idx, task in enumerate(asyncio.all_tasks(self._loop)):
                logger.debug(f"AsyncWorker: Cancelling task {task_idx} in loop for {getattr(self.async_fn, '__name__', 'unknown')}")
                task.cancel()
            self._loop.call_soon_threadsafe(self._loop.stop)
        else:
            logger.debug(f"AsyncWorker: Loop not running or not set for {getattr(self.async_fn, '__name__', 'unknown')}")

# TaskManager and AsyncTaskManager classes remain unchanged from user's provided version
class TaskManager:
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(max_workers)
        self.active_tasks: Dict[str, Union[Worker, AsyncWorker]] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self._task_counter = 0
        self._lock = threading.Lock()
    def _generate_task_id(self) -> str:
        with self._lock: self._task_counter += 1; return f"task_{self._task_counter}_{int(time.time())}"
    def run_task(self, fn: Callable, *args, task_name: Optional[str]=None, on_result: Optional[Callable]=None, on_error: Optional[Callable]=None, **kwargs) -> str:
        task_id = self._generate_task_id(); task_name = task_name or f"Task {task_id}"; worker = Worker(fn, *args, **kwargs)
        if on_result: worker.signals.result.connect(on_result)
        if on_error: worker.signals.error.connect(on_error)
        worker.signals.finished.connect(lambda: self._task_completed(task_id, task_name))
        self.active_tasks[task_id] = worker; self.thread_pool.start(worker)
        logger.debug(f"Started task {task_id}: {task_name}"); return task_id
    def run_async_task(self, async_fn: Callable, *args, task_name: Optional[str]=None, on_result: Optional[Callable]=None, on_error: Optional[Callable]=None, **kwargs) -> str:
        task_id = self._generate_task_id(); task_name = task_name or f"AsyncTask {task_id}"; worker = AsyncWorker(async_fn, *args, **kwargs)
        if on_result: worker.result_ready.connect(on_result)
        if on_error: worker.error_occurred.connect(on_error)
        worker.finished.connect(lambda: self._task_completed(task_id, task_name))
        self.active_tasks[task_id] = worker; worker.start()
        logger.debug(f"Started async task {task_id}: {task_name}"); return task_id
    def cancel_task(self, task_id: str) -> bool:
        if task_id in self.active_tasks: self.active_tasks[task_id].cancel(); logger.debug(f"Cancelled task {task_id}"); return True
        return False
    def _task_completed(self, task_id: str, task_name: str):
        if task_id in self.active_tasks: del self.active_tasks[task_id]
        logger.debug(f"Completed task {task_id}: {task_name}")
    def get_active_task_count(self) -> int: return len(self.active_tasks)
    def cancel_all_tasks(self):
        for task_id in list(self.active_tasks.keys()): self.cancel_task(task_id)
        logger.info("Cancelled all active tasks")
    def shutdown(self): self.cancel_all_tasks(); self.thread_pool.waitForDone(5000); logger.info("TaskManager shutdown complete")

class AsyncTaskManager:
    def __init__(self, max_concurrent_tasks: int = 10):
        self.max_concurrent_tasks = max_concurrent_tasks; self.active_tasks: Dict[str, asyncio.Task] = {}; self.task_results: Dict[str, TaskResult] = {}
        self._task_counter = 0; self._lock = asyncio.Lock(); self._executor = ThreadPoolExecutor(max_workers=4)
    async def _generate_task_id(self) -> str:
        async with self._lock: self._task_counter += 1; return f"async_task_{self._task_counter}_{int(time.time())}"
    async def run_async_task(self, coro_fn: Callable, *args, task_name: Optional[str]=None, **kwargs) -> str:
        task_id = await self._generate_task_id(); task_name = task_name or f"AsyncTask {task_id}"
        async def wrapped_task():
            start_time = time.time()
            try:
                result = await coro_fn(*args, **kwargs)
                self.task_results[task_id] = TaskResult(task_id=task_id, success=True, result=result, execution_time=time.time()-start_time)
                return result
            except Exception as e:
                self.task_results[task_id] = TaskResult(task_id=task_id, success=False, error=e, execution_time=time.time()-start_time)
                logger.error(f"Async task {task_id} failed: {e}", exc_info=True); raise
            finally:
                if task_id in self.active_tasks: del self.active_tasks[task_id]
        task = asyncio.create_task(wrapped_task(), name=task_name); self.active_tasks[task_id] = task
        logger.debug(f"Started async task {task_id}: {task_name}"); return task_id
    async def run_sync_task(self, fn: Callable, *args, task_name: Optional[str]=None, **kwargs) -> str:
        task_id = await self._generate_task_id(); task_name = task_name or f"SyncTask {task_id}"; loop = asyncio.get_running_loop()
        async def wrapped_task():
            start_time = time.time()
            try:
                result = await loop.run_in_executor(self._executor, fn, *args)
                self.task_results[task_id] = TaskResult(task_id=task_id, success=True, result=result, execution_time=time.time()-start_time)
                return result
            except Exception as e:
                self.task_results[task_id] = TaskResult(task_id=task_id, success=False, error=e, execution_time=time.time()-start_time)
                logger.error(f"Sync task {task_id} failed: {e}", exc_info=True); raise
            finally:
                if task_id in self.active_tasks: del self.active_tasks[task_id]
        task = asyncio.create_task(wrapped_task(), name=task_name); self.active_tasks[task_id] = task
        logger.debug(f"Started sync task {task_id}: {task_name}"); return task_id
    async def cancel_task(self, task_id: str) -> bool:
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]; task.cancel()
            try: await task
            except asyncio.CancelledError: pass
            logger.debug(f"Cancelled async task {task_id}"); return True
        return False
    async def wait_for_task(self, task_id: str, timeout: Optional[float]=None) -> Optional[TaskResult]:
        if task_id in self.active_tasks:
            try: await asyncio.wait_for(self.active_tasks[task_id], timeout=timeout)
            except asyncio.TimeoutError: logger.warning(f"Task {task_id} timed out"); return None
        return self.task_results.get(task_id)
    def get_task_result(self, task_id: str) -> Optional[TaskResult]: return self.task_results.get(task_id)
    def get_active_task_count(self) -> int: return len(self.active_tasks)
    async def cancel_all_tasks(self):
        tasks_to_cancel = list(self.active_tasks.values());_=[task.cancel() for task in tasks_to_cancel]
        if tasks_to_cancel: await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        self.active_tasks.clear(); logger.info("Cancelled all async tasks")
    def shutdown(self):
        for task in self.active_tasks.values(): task.cancel()
        self._executor.shutdown(wait=False); logger.info("AsyncTaskManager shutdown complete")

_task_manager: Optional[TaskManager] = None
_async_task_manager: Optional[AsyncTaskManager] = None
def get_task_manager() -> TaskManager:
    global _task_manager
    if _task_manager is None: _task_manager = TaskManager()
    return _task_manager
def get_async_task_manager() -> AsyncTaskManager:
    global _async_task_manager
    if _async_task_manager is None: _async_task_manager = AsyncTaskManager()
    return _async_task_manager
def run_in_background(fn: Callable, *args, task_name: Optional[str]=None, on_result: Optional[Callable]=None, on_error: Optional[Callable]=None, **kwargs) -> str:
    return get_task_manager().run_task(fn, *args, task_name=task_name, on_result=on_result, on_error=on_error, **kwargs)
async def run_async_in_background(async_fn: Callable, *args, task_name: Optional[str]=None, **kwargs) -> str:
    return await get_async_task_manager().run_async_task(async_fn, *args, task_name=task_name, **kwargs)
