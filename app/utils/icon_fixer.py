# Implementation for fixing missing icons
# Create a script to check and download missing icons

import os
import requests
import logging
from PyQt6.QtWidgets import QMessageBox, QApplication

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("icon_fixer")

def check_and_fix_icons(app_root, icon_resources=None):
    """
    Checks for missing icons and attempts to fix them.
    
    Args:
        app_root (str): The root directory of the application
        icon_resources (dict, optional): Dict mapping icon names to URLs for download
        
    Returns:
        tuple: (fixed_count, missing_count)
    """
    if icon_resources is None:
        # Default icon resources - replace with actual URLs as needed
        icon_resources = {
            "invoice_icon.png": "https://example.com/default-icons/invoice_icon.png",
            "app_icon.png": "https://example.com/default-icons/app_icon.png",
            # Add more icons as needed
        }
    
    # Make sure the icons directory exists
    icons_dir = os.path.join(app_root, "resources", "icons")
    os.makedirs(icons_dir, exist_ok=True)
    
    # Check all standard icons
    fixed_count = 0
    missing_count = 0
    
    for icon_name, icon_url in icon_resources.items():
        icon_path = os.path.join(icons_dir, icon_name)
        
        if not os.path.exists(icon_path):
            logger.warning(f"Missing icon: {icon_name}")
            missing_count += 1
            
            # Try to download the icon
            try:
                logger.info(f"Attempting to download {icon_name}")
                response = requests.get(icon_url, timeout=10)
                
                if response.status_code == 200:
                    with open(icon_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Successfully downloaded {icon_name}")
                    fixed_count += 1
                else:
                    logger.error(f"Failed to download {icon_name}: HTTP {response.status_code}")
            except Exception as e:
                logger.error(f"Error downloading {icon_name}: {e}")
    
    # Create a fallback icon if any icons are still missing
    create_fallback_icons(icons_dir)
    
    return fixed_count, missing_count

def create_fallback_icons(icons_dir):
    """
    Creates fallback icons for common icons that might be missing.
    
    Args:
        icons_dir (str): Path to the icons directory
    """
    # List of essential icons
    essential_icons = [
        "invoice_icon.png", 
        "app_icon.png",
        "calculator_icon.png",
        "deals_icon.png", 
        "inventory_icon.png"
    ]
    
    # Check if each essential icon exists, if not create a basic one
    for icon_name in essential_icons:
        icon_path = os.path.join(icons_dir, icon_name)
        
        if not os.path.exists(icon_path):
            # Create a basic icon using Qt
            try:
                from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
                from PyQt6.QtCore import Qt
                
                # Generate a simple colored square with text
                pixmap = QPixmap(64, 64)
                pixmap.fill(QColor(100, 149, 237))  # Cornflower blue
                
                painter = QPainter(pixmap)
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Arial", 20, QFont.Weight.Bold))
                
                # Use the first letter as the icon text
                text = icon_name[0].upper()
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
                painter.end()
                
                # Save the pixmap
                pixmap.save(icon_path)
                logger.info(f"Created fallback icon for {icon_name}")
            except Exception as e:
                logger.error(f"Error creating fallback icon for {icon_name}: {e}")

if __name__ == "__main__":
    # When run as a script, this will fix icons in the current directory
    app = QApplication([])  # Needed for QPixmap
    
    app_root = os.path.abspath(".")
    fixed, missing = check_and_fix_icons(app_root)
    
    print(f"Icon check completed. Fixed: {fixed}, Still missing: {missing - fixed}")