# utils/csv_handler.py
import csv
import os
import logging
from typing import List, Dict, Any, Optional, Union, Tuple

logger = logging.getLogger(__name__)

class CSVHandler:
    """Utility class for CSV file operations with robust error handling and encoding detection."""
    
    def __init__(self, data_path=None):
        """Initialize the CSV handler.
        
        Args:
            data_path: Base directory for CSV files
        """
        self.data_path = data_path
        if not self.data_path:
            logger.warning("No data_path provided to CSVHandler, file paths must be absolute")
    
    def _get_file_path(self, filename):
        """Get absolute file path for a CSV file.
        
        Args:
            filename: CSV filename
            
        Returns:
            Absolute file path
        """
        if os.path.isabs(filename):
            return filename
            
        if not self.data_path:
            logger.warning(f"No data_path set, using relative path for {filename}")
            return filename
            
        return os.path.join(self.data_path, filename)
    
    def load_csv(self, filename, skip_header=False, encodings=None):
        """Load CSV data into a list of rows.
        
        Args:
            filename: CSV filename
            skip_header: Whether to skip the first row (header)
            encodings: List of encodings to try
            
        Returns:
            List of rows or None if failed
        """
        file_path = self._get_file_path(filename)
        if not os.path.exists(file_path):
            logger.error(f"CSV file not found: {file_path}")
            return None
            
        if encodings is None:
            encodings = ['utf-8', 'latin1', 'windows-1252']
            
        for encoding in encodings:
            try:
                logger.debug(f"Trying to read {filename} with encoding '{encoding}'...")
                with open(file_path, mode='r', newline='', encoding=encoding) as f:
                    reader = csv.reader(f)
                    if skip_header:
                        next(reader, None)  # Skip header
                    
                    rows = list(reader)
                    logger.info(f"Successfully loaded {len(rows)} rows from {filename} with encoding '{encoding}'")
                    return rows
            except UnicodeDecodeError:
                logger.debug(f"Failed to decode {filename} with encoding '{encoding}'")
                continue
            except Exception as e:
                logger.error(f"Error reading CSV file {filename}: {str(e)}")
                return None
                
        logger.error(f"Failed to decode {filename} with any of the encodings: {encodings}")
        return None
    
    def load_csv_dict(self, filename, key_column, value_column=None, encodings=None):
        """Load CSV data into a dictionary.
        
        Args:
            filename: CSV filename
            key_column: Column to use as dictionary keys
            value_column: Column to use as dictionary values (if None, entire row is used)
            encodings: List of encodings to try
            
        Returns:
            Dictionary of CSV data or empty dict if failed
        """
        file_path = self._get_file_path(filename)
        if not os.path.exists(file_path):
            logger.error(f"CSV file not found: {file_path}")
            return {}
            
        if encodings is None:
            encodings = ['utf-8', 'latin1', 'windows-1252']
            
        for encoding in encodings:
            try:
                logger.debug(f"Trying to read {filename} with encoding '{encoding}'...")
                with open(file_path, mode='r', newline='', encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    result = {}
                    
                    # Convert field names to lowercase for case-insensitive matching
                    field_names_lower = {field.lower(): field for field in reader.fieldnames} if reader.fieldnames else {}
                    
                    # Get actual column names
                    key_col = field_names_lower.get(key_column.lower(), key_column)
                    val_col = field_names_lower.get(value_column.lower(), value_column) if value_column else None
                    
                    for row in reader:
                        if key_col not in row:
                            logger.warning(f"Key column '{key_col}' not found in row: {row}")
                            continue
                            
                        key = row[key_col].strip()
                        if not key:
                            continue  # Skip empty keys
                            
                        if val_col:
                            if val_col not in row:
                                logger.warning(f"Value column '{val_col}' not found in row: {row}")
                                continue
                                
                            result[key] = row[val_col].strip()
                        else:
                            result[key] = {k: v.strip() for k, v in row.items()}
                    
                    logger.info(f"Successfully loaded {len(result)} items from {filename} with encoding '{encoding}'")
                    return result
            except UnicodeDecodeError:
                logger.debug(f"Failed to decode {filename} with encoding '{encoding}'")
                continue
            except Exception as e:
                logger.error(f"Error reading CSV file {filename}: {str(e)}")
                return {}
                
        logger.error(f"Failed to decode {filename} with any of the encodings: {encodings}")
        return {}
    
    def save_csv(self, filename, rows, headers=None):
        """Save data to a CSV file.
        
        Args:
            filename: CSV filename
            rows: List of rows to save
            headers: List of column headers
            
        Returns:
            True if successful, False otherwise
        """
        file_path = self._get_file_path(filename)
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if headers:
                    writer.writerow(headers)
                writer.writerows(rows)
            
            logger.info(f"Successfully saved {len(rows)} rows to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving CSV file {filename}: {str(e)}")
            return False
    
    def save_csv_dict(self, filename, data, headers=None):
        """Save dictionary data to a CSV file.
        
        Args:
            filename: CSV filename
            data: List of dictionaries to save
            headers: List of column headers (if None, use keys from first dictionary)
            
        Returns:
            True if successful, False otherwise
        """
        file_path = self._get_file_path(filename)
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            if not data:
                logger.warning(f"No data to save to {filename}")
                return False
                
            if not headers and isinstance(data[0], dict):
                headers = list(data[0].keys())
                
            with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            
            logger.info(f"Successfully saved {len(data)} rows to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving CSV file {filename}: {str(e)}")
            return False

def load_csv_to_dataframe(file_path, encoding='utf-8'):
    """
    Load a CSV file into a pandas DataFrame.
    
    Args:
        file_path (str): Path to the CSV file
        encoding (str): File encoding, defaults to 'utf-8'
        
    Returns:
        pandas.DataFrame: DataFrame containing the CSV data
    """
    import pandas as pd
    try:
        return pd.read_csv(file_path, encoding=encoding)
    except UnicodeDecodeError:
        # Fallback encodings
        for enc in ['latin1', 'windows-1252', 'utf-8-sig']:
            try:
                return pd.read_csv(file_path, encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode the CSV file {file_path} with any supported encoding")