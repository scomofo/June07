# app/utils/resource_checker.py
import os
import logging

logger = logging.getLogger(__name__)

def check_resources(config_obj=None):
    """
    Check and fix application resources on startup.
    
    Args:
        config_obj: Application config object (optional)
    """
    try:
        # Just use the current working directory as app_root if no config provided
        app_root = os.getcwd()
        
        # Try to get project root from config if available
        if config_obj is not None:
            try:
                # Check if it's a dict-like object
                if hasattr(config_obj, 'get') and callable(config_obj.get):
                    if config_obj.get("PROJECT_ROOT"):
                        app_root = config_obj.get("PROJECT_ROOT")
            except Exception as e:
                logger.warning(f"Error accessing config: {e}")
        
        logger.info(f"Using project root directory: {app_root}")
        
        # Check and fix CSV headers
        logger.info("Checking CSV headers...")
        try:
            from app.utils.csv_header_fixer import fix_csv_headers
            csv_results = fix_csv_headers(app_root_dir=app_root)
            
            # Summarize CSV results
            success_count = sum(1 for result in csv_results.values() if result.get("success"))
            logger.info(f"CSV header check completed: {success_count}/{len(csv_results)} files processed successfully")
        except ImportError as e:
            logger.error(f"Could not import CSV header fixer module: {e}")
        except Exception as e:
            logger.error(f"Error during CSV header check: {e}", exc_info=True)
        
        return True
    except Exception as e:
        logger.error(f"Error during resource check: {e}", exc_info=True)
        return False