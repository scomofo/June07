# bridleal_refactored/app/utils/csv_utils.py
import csv
import os
import logging
import shutil 
from datetime import datetime 

logger = logging.getLogger(__name__)

class CsvUtils:
    """
    A utility class providing helper functions for CSV file operations.
    """

    @staticmethod
    def read_csv_to_list_of_dicts(filepath: str, encoding='utf-8') -> list[dict] | None:
        """
        Reads a CSV file into a list of dictionaries.
        The first row of the CSV is assumed to be the header row (keys for the dicts).
        """
        if not os.path.exists(filepath):
            logger.warning(f"CSV file not found for reading: {filepath}")
            return None
        
        data = []
        try:
            with open(filepath, mode='r', newline='', encoding=encoding) as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    data.append(dict(row)) 
            logger.info(f"Successfully read {len(data)} rows from CSV: {filepath}")
            return data
        except Exception as e:
            logger.error(f"Error reading CSV file {filepath} into list of dicts: {e}", exc_info=True)
            return None

    @staticmethod
    def write_list_of_dicts_to_csv(filepath: str, data: list[dict], headers: list[str] = None, encoding='utf-8', write_header=True) -> bool:
        """
        Writes a list of dictionaries to a CSV file.
        """
        if not data:
            logger.warning(f"No data provided to write to CSV: {filepath}. Writing an empty file or only headers if specified.")
            
        if not headers and data:
            headers = list(data[0].keys()) 
        elif not headers and not data and write_header:
            logger.warning(f"Cannot write headers for {filepath} as no data and no explicit headers provided.")
            if not write_header: 
                 try:
                    # Ensure directory exists before trying to create the file
                    file_dir = os.path.dirname(filepath)
                    if file_dir: # Check if dirname is not empty
                        os.makedirs(file_dir, exist_ok=True)
                    with open(filepath, mode='w', newline='', encoding=encoding) as csvfile:
                        pass 
                    logger.info(f"Created empty CSV file (no data, no headers written): {filepath}")
                    return True
                 except Exception as e:
                    logger.error(f"Error creating empty CSV file {filepath}: {e}", exc_info=True)
                    return False
            else: 
                logger.error(f"Cannot write CSV {filepath}: No data and no headers specified to write header row.")
                return False
        elif not headers and write_header: 
             logger.info(f"Writing CSV {filepath} with headers only (no data).")
             # This case will be handled by the main try-except block if headers are actually an empty list.
             # If headers is None but write_header is true, it's an issue.
             # The logic below handles if `headers` is an empty list when `write_header` is true.
             # If `headers` is `None` and `write_header` is `True`, it should fail or log error.
             if headers is None: # Explicitly check for None if write_header is True
                logger.error(f"Cannot write header for {filepath}: headers list is None but write_header is True.")
                return False


        try:
            file_dir = os.path.dirname(filepath)
            if file_dir: # Check if dirname is not empty
                os.makedirs(file_dir, exist_ok=True) 
            
            with open(filepath, mode='w', newline='', encoding=encoding) as csvfile:
                # fieldnames must be provided to DictWriter if writing headers or data
                current_headers = headers
                if not current_headers and data: # Infer from data if headers still None but data exists
                    current_headers = list(data[0].keys())
                elif not current_headers and not data and not write_header: # No data, no headers, not writing header -> empty file
                    logger.info(f"Writing completely empty CSV file (no data, no headers): {filepath}")
                    return True # Successfully created an empty file
                elif not current_headers and write_header: # Trying to write header but no headers known
                    logger.error(f"Cannot write header for {filepath}: headers list is empty/None.")
                    return False


                writer = csv.DictWriter(csvfile, fieldnames=current_headers if current_headers else [])
                if write_header:
                    writer.writeheader()
                if data: 
                    writer.writerows(data)
            logger.info(f"Successfully wrote {len(data) if data else 0} rows to CSV: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error writing list of dicts to CSV file {filepath}: {e}", exc_info=True)
            return False

    @staticmethod
    def read_csv_to_list_of_lists(filepath: str, encoding='utf-8', skip_header=False) -> list[list[str]] | None:
        """
        Reads a CSV file into a list of lists.
        """
        if not os.path.exists(filepath):
            logger.warning(f"CSV file not found for reading: {filepath}")
            return None
        
        data = []
        try:
            with open(filepath, mode='r', newline='', encoding=encoding) as csvfile:
                reader = csv.reader(csvfile)
                if skip_header:
                    try:
                        next(reader) 
                    except StopIteration:
                        logger.warning(f"CSV file {filepath} is empty, cannot skip header.")
                        return [] 
                for row in reader:
                    data.append(row)
            logger.info(f"Successfully read {len(data)} rows (as lists) from CSV: {filepath}")
            return data
        except Exception as e:
            logger.error(f"Error reading CSV file {filepath} into list of lists: {e}", exc_info=True)
            return None

    @staticmethod
    def write_list_of_lists_to_csv(filepath: str, data: list[list[str]], headers: list[str] = None, encoding='utf-8') -> bool:
        """
        Writes a list of lists to a CSV file.
        """
        try:
            file_dir = os.path.dirname(filepath)
            if file_dir: # Check if dirname is not empty
                os.makedirs(file_dir, exist_ok=True) 
            with open(filepath, mode='w', newline='', encoding=encoding) as csvfile:
                writer = csv.writer(csvfile)
                if headers:
                    writer.writerow(headers)
                writer.writerows(data) # writerows handles empty data list correctly
            logger.info(f"Successfully wrote {len(data)} rows (from lists) to CSV: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error writing list of lists to CSV file {filepath}: {e}", exc_info=True)
            return False

    @staticmethod
    def ensure_csv_headers(file_path: str, expected_headers: list, backup: bool = True, create_if_missing: bool = True, encoding: str = 'utf-8') -> bool:
        """
        Ensures a CSV file has the expected headers. If the file exists with different headers,
        it can create a backup and update the headers. If the file doesn't exist and
        create_if_missing is True, it creates the file with the expected headers.
        """
        dir_name = os.path.dirname(file_path)
        if dir_name: 
            os.makedirs(dir_name, exist_ok=True)

        if not os.path.exists(file_path):
            if not create_if_missing:
                logger.warning(f"CSV file {file_path} not found and create_if_missing=False.")
                return False
            try:
                with open(file_path, 'w', newline='', encoding=encoding) as f:
                    writer = csv.writer(f)
                    writer.writerow(expected_headers)
                logger.info(f"Created new CSV file {file_path} with expected headers: {expected_headers}")
                return True
            except Exception as e:
                logger.error(f"Error creating CSV file {file_path} with headers: {e}", exc_info=True)
                return False
        
        existing_headers = []
        try:
            with open(file_path, 'r', newline='', encoding=encoding) as f:
                reader = csv.reader(f)
                existing_headers = next(reader, []) 
        except StopIteration: 
            logger.warning(f"CSV file {file_path} is empty. Will attempt to write headers.")
        except Exception as e:
            logger.error(f"Error reading CSV headers from {file_path}: {e}", exc_info=True)
            return False 
        
        normalized_existing = [str(h).strip().lower() for h in existing_headers]
        normalized_expected = [str(h).strip().lower() for h in expected_headers]

        if normalized_existing == normalized_expected:
            logger.debug(f"CSV file {file_path} already has expected headers.")
            return True
        
        logger.warning(f"CSV headers mismatch in {file_path}. Expected {expected_headers} (normalized: {normalized_expected}), got {existing_headers} (normalized: {normalized_existing}).")
        
        if backup:
            backup_path = f"{file_path}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            try:
                shutil.copy2(file_path, backup_path)
                logger.info(f"Created backup of CSV file at {backup_path}")
            except Exception as e:
                logger.error(f"Error creating backup of {file_path}: {e}", exc_info=True)
        
        data_rows = []
        if existing_headers: 
            try:
                with open(file_path, 'r', newline='', encoding=encoding) as f:
                    reader = csv.reader(f)
                    next(reader, None) 
                    data_rows = list(reader)
                logger.info(f"Read {len(data_rows)} data rows from {file_path} before header update.")
            except Exception as e:
                logger.error(f"Error reading CSV data rows from {file_path} for header update: {e}", exc_info=True)
                return False 
        
        try:
            with open(file_path, 'w', newline='', encoding=encoding) as f:
                writer = csv.writer(f)
                writer.writerow(expected_headers) 
                if data_rows:
                    writer.writerows(data_rows) 
            logger.info(f"Updated CSV file {file_path} with expected headers and {len(data_rows)} data rows.")
            return True
        except Exception as e:
            logger.error(f"Error writing updated headers and data to CSV file {file_path}: {e}", exc_info=True)
            return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s')
    
    test_data_dir = "test_csv_utils_data"
    os.makedirs(test_data_dir, exist_ok=True)

    dict_csv_file = os.path.join(test_data_dir, "test_dict_data.csv")
    list_csv_file = os.path.join(test_data_dir, "test_list_data.csv")
    empty_header_csv_file = os.path.join(test_data_dir, "empty_header.csv")
    ensure_test_file = os.path.join(test_data_dir, "ensure_headers_test.csv")
    ensure_test_file_no_create = os.path.join(test_data_dir, "ensure_headers_test_nocreate.csv")

    sample_data_dicts = [
        {"id": "1", "name": "Alice", "age": "30", "city": "New York"},
        {"id": "2", "name": "Bob", "age": "24", "city": "Los Angeles"},
        {"id": "3", "name": "Charlie", "age": "35", "city": "Chicago"}
    ]
    custom_headers = ["id", "name", "age", "city"] 

    sample_data_lists = [
        ["product_id", "product_name", "price"], 
        ["P101", "Laptop", "1200.00"],
        ["P102", "Mouse", "25.00"],
        ["P103", "Keyboard", "75.00"]
    ]

    logger.info(f"\n--- Testing write_list_of_dicts_to_csv to {dict_csv_file} ---")
    success_write_dict = CsvUtils.write_list_of_dicts_to_csv(dict_csv_file, sample_data_dicts, headers=custom_headers)
    assert success_write_dict, "Failed to write dicts to CSV"

    logger.info(f"\n--- Testing read_csv_to_list_of_dicts from {dict_csv_file} ---")
    read_data_dicts = CsvUtils.read_csv_to_list_of_dicts(dict_csv_file)
    assert read_data_dicts == sample_data_dicts, "Data mismatch when reading dicts from CSV"
    if read_data_dicts:
        logger.info(f"Read data (dicts): {read_data_dicts[0]}")

    logger.info(f"\n--- Testing write_list_of_lists_to_csv to {list_csv_file} ---")
    list_headers = sample_data_lists[0]
    list_data_rows = sample_data_lists[1:]
    success_write_list = CsvUtils.write_list_of_lists_to_csv(list_csv_file, list_data_rows, headers=list_headers)
    assert success_write_list, "Failed to write lists to CSV"

    logger.info(f"\n--- Testing read_csv_to_list_of_lists from {list_csv_file} (including header) ---")
    read_data_lists_with_header = CsvUtils.read_csv_to_list_of_lists(list_csv_file, skip_header=False)
    assert read_data_lists_with_header == sample_data_lists, "Data mismatch when reading lists (with header) from CSV"
    if read_data_lists_with_header:
        logger.info(f"Read data (lists with header): {read_data_lists_with_header[0]}")

    logger.info(f"\n--- Testing read_csv_to_list_of_lists from {list_csv_file} (skipping header) ---")
    read_data_lists_no_header = CsvUtils.read_csv_to_list_of_lists(list_csv_file, skip_header=True)
    assert read_data_lists_no_header == list_data_rows, "Data mismatch when reading lists (no header) from CSV"
    if read_data_lists_no_header:
        logger.info(f"Read data (lists no header): {read_data_lists_no_header[0]}")

    logger.info(f"\n--- Testing writing empty file with only headers to {empty_header_csv_file} ---")
    empty_headers = ["colA", "colB", "colC"]
    success_empty_header = CsvUtils.write_list_of_dicts_to_csv(empty_header_csv_file, [], headers=empty_headers)
    assert success_empty_header, "Failed to write empty CSV with headers"
    if os.path.exists(empty_header_csv_file):
        with open(empty_header_csv_file, 'r') as f:
            content = f.read().strip()
            assert content == ",".join(empty_headers), f"Content mismatch for empty header file. Got: '{content}'"
            logger.info(f"Content of {empty_header_csv_file}: '{content}'")
    
    logger.info(f"\n--- Testing ensure_csv_headers on non-existent file (create_if_missing=True) ---")
    expected_test_headers = ["Header1", "Header2", "Header3"]
    if os.path.exists(ensure_test_file): os.remove(ensure_test_file)
    success_ensure_create = CsvUtils.ensure_csv_headers(ensure_test_file, expected_test_headers, create_if_missing=True)
    assert success_ensure_create, "ensure_csv_headers failed to create file"
    assert os.path.exists(ensure_test_file), "ensure_csv_headers did not create the file"
    read_back_headers = CsvUtils.read_csv_to_list_of_lists(ensure_test_file)
    assert read_back_headers and read_back_headers[0] == expected_test_headers, "Created file headers mismatch"

    logger.info(f"\n--- Testing ensure_csv_headers on existing file with correct headers ---")
    success_ensure_correct = CsvUtils.ensure_csv_headers(ensure_test_file, expected_test_headers)
    assert success_ensure_correct, "ensure_csv_headers failed on correct headers"

    logger.info(f"\n--- Testing ensure_csv_headers on existing file with incorrect headers (and backup) ---")
    wrong_headers = ["Wrong1", "Wrong2"]
    with open(ensure_test_file, 'w', newline='') as f:
        writer = csv.writer(f); writer.writerow(wrong_headers); writer.writerow(["d1","d2"])
    success_ensure_fix = CsvUtils.ensure_csv_headers(ensure_test_file, expected_test_headers, backup=True)
    assert success_ensure_fix, "ensure_csv_headers failed to fix headers"
    read_back_fixed_headers = CsvUtils.read_csv_to_list_of_lists(ensure_test_file)
    assert read_back_fixed_headers and read_back_fixed_headers[0] == expected_test_headers, "Fixed file headers mismatch"
    assert read_back_fixed_headers and len(read_back_fixed_headers) > 1 and read_back_fixed_headers[1] == ["d1","d2"], "Data not preserved after header fix"
    backup_found = any(f.startswith(os.path.basename(ensure_test_file) + ".") and f.endswith(".bak") for f in os.listdir(test_data_dir))
    assert backup_found, "Backup file not created"

    logger.info(f"\n--- Testing ensure_csv_headers on non-existent file (create_if_missing=False) ---")
    if os.path.exists(ensure_test_file_no_create): os.remove(ensure_test_file_no_create)
    success_ensure_no_create = CsvUtils.ensure_csv_headers(ensure_test_file_no_create, expected_test_headers, create_if_missing=False)
    assert not success_ensure_no_create, "ensure_csv_headers created file when create_if_missing=False"
    assert not os.path.exists(ensure_test_file_no_create), "ensure_csv_headers created file when it should not have"

    logger.info("\nCsvUtils tests completed.")
    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir)
        logger.info(f"Cleaned up test data directory: {test_data_dir}")
