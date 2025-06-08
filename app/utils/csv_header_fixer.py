# app/utils/csv_header_fixer.py
import os
import csv 
import logging
from app.utils.csv_utils import CsvUtils 

logger = logging.getLogger(__name__)

def fix_csv_headers(app_root_dir=None):
    """
    Ensure headers in common CSV files used by the application match the specified definitions.
    
    Args:
        app_root_dir (str, optional): Root directory of the application.
            If None, will use the current working directory.
    
    Returns:
        dict: A summary of the files processed and their status
    """
    if app_root_dir is None:
        app_root_dir = os.getcwd()
        logger.info(f"No app_root_dir provided, using current working directory: {app_root_dir}")
    else:
        logger.info(f"Using provided app_root_dir: {app_root_dir}")
    
    data_dir = os.path.join(app_root_dir, "data")
    app_module_data_dir = os.path.join(app_root_dir, "app", "views", "modules", "data")
    
    logger.info(f"Main data directory resolved to: {os.path.abspath(data_dir)}")
    logger.info(f"App module data directory resolved to: {os.path.abspath(app_module_data_dir)}")

    header_definitions = {
        os.path.join(data_dir, "customers.csv"): ['Name', 'CustomerNumber'],
        os.path.join(data_dir, "products.csv"): ['ProductCode', 'ProductName', 'Price', 'JDQName'],
        os.path.join(data_dir, "parts.csv"): ['Part Number', 'Part Name'],
        os.path.join(data_dir, "salesmen.csv"): ['Name', 'Email', 'XiD'],
        os.path.join(app_module_data_dir, "customers.csv"): ['Name', 'CustomerNumber'],
        os.path.join(app_module_data_dir, "products.csv"): ['ProductCode', 'ProductName', 'Price', 'JDQName'],
        os.path.join(app_module_data_dir, "parts.csv"): ['Part Number', 'Part Name'],
        os.path.join(app_module_data_dir, "salesmen.csv"): ['Name', 'Email', 'XiD'],
    }
    
    results = {}
    
    if not (hasattr(CsvUtils, 'ensure_csv_headers') and callable(getattr(CsvUtils, 'ensure_csv_headers'))):
        logger.error("CsvUtils.ensure_csv_headers method is not available or not callable. Cannot perform header fixing.")
        for file_path_key in header_definitions:
            results[file_path_key] = {
                "success": False,
                "expected_headers": header_definitions[file_path_key],
                "exists_after_check": os.path.exists(file_path_key), # Check current existence
                "error": "CsvUtils.ensure_csv_headers not available."
            }
        success_count = 0
        logger.info(f"CSV header fix summary: {success_count}/{len(results)} files processed successfully (CsvUtils.ensure_csv_headers missing).")
        return results

    for file_path, expected_headers in header_definitions.items():
        abs_file_path = os.path.abspath(file_path)
        try:
            logger.info(f"Checking headers for: {file_path} (Absolute: {abs_file_path})")
            
            file_dir = os.path.dirname(file_path)
            if not os.path.exists(file_dir):
                logger.info(f"Directory {file_dir} does not exist. Attempting to create it.")
                os.makedirs(file_dir, exist_ok=True)
            
            # Call as a static method
            success = CsvUtils.ensure_csv_headers(
                file_path=file_path,
                expected_headers=expected_headers,
                backup=True,
                create_if_missing=True 
            )

            results[file_path] = {
                "success": success,
                "expected_headers": expected_headers,
                "exists_after_check": os.path.exists(file_path) 
            }
            
            if success:
                logger.info(f"Successfully ensured headers for: {file_path}")
            else:
                logger.error(f"Failed to ensure headers for: {file_path} (CsvUtils.ensure_csv_headers returned False)")
                
        except AttributeError as ae: 
            logger.error(f"AttributeError calling CsvUtils.ensure_csv_headers for {file_path}: {str(ae)}.", exc_info=True)
            results[file_path] = { "success": False, "expected_headers": expected_headers, "exists_after_check": os.path.exists(file_path), "error": str(ae) }
        except Exception as e:
            logger.error(f"Unexpected error processing {file_path}: {str(e)}", exc_info=True)
            results[file_path] = { "success": False, "expected_headers": expected_headers, "exists_after_check": os.path.exists(file_path), "error": str(e) }
    
    success_count = sum(1 for result in results.values() if result.get("success"))
    logger.info(f"CSV header fix summary: {success_count}/{len(results)} files processed successfully")
    
    return results

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s'
    )
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logger.info(f"Running csv_header_fixer.py standalone with project root: {project_root}")

    real_CsvUtils_imported = False
    try:
        from app.utils.csv_utils import CsvUtils
        real_CsvUtils_imported = True
        logger.info("Successfully imported app.utils.csv_utils.CsvUtils for standalone test.")
    except ImportError:
        logger.warning("Could not import app.utils.csv_utils. Using a MockCsvUtils for standalone testing.")
        
        class MockCsvUtils: # Renamed to avoid conflict if real one is imported later
            @staticmethod
            def ensure_csv_headers(file_path, expected_headers, backup=True, create_if_missing=True):
                logger.info(f"[MockCsvUtils] Ensuring headers for {file_path} with headers: {expected_headers}")
                file_dir = os.path.dirname(file_path)
                if not os.path.exists(file_dir):
                    os.makedirs(file_dir, exist_ok=True)
                    logger.info(f"[MockCsvUtils] Created directory: {file_dir}")

                if not os.path.exists(file_path) and create_if_missing:
                    try:
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(expected_headers)
                        logger.info(f"[MockCsvUtils] Created missing file with headers: {file_path}")
                        return True
                    except Exception as e_write:
                        logger.error(f"[MockCsvUtils] Error creating file {file_path}: {e_write}")
                        return False
                elif os.path.exists(file_path):
                    logger.info(f"[MockCsvUtils] File {file_path} exists. Assuming headers are OK for mock.")
                    return True
                return False
        
        if not real_CsvUtils_imported:
            # This is a more robust way to ensure CsvUtils is the mock if the real one fails
            # It avoids trying to modify sys.modules directly which can be tricky.
            CsvUtils = MockCsvUtils 

    results = fix_csv_headers(app_root_dir=project_root) 
    
    print("\n=== CSV Header Fix Summary ===")
    for file_path, result in results.items():
        status = "SUCCESS" if result.get("success") else "FAILED"
        error_msg = f" Error: {result['error']}" if "error" in result and not result.get("success") else ""
        try:
            relative_path = os.path.relpath(file_path, project_root)
        except ValueError: 
            relative_path = file_path
        print(f"{relative_path}: {status}{error_msg}") 
    
    success_count = sum(1 for result in results.values() if result.get("success"))
    print(f"\nTotal: {success_count}/{len(results)} files processed successfully")
