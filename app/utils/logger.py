import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name, log_file, level=logging.INFO):
    """Configure un logger avec rotation des fichiers"""
    
    # Create the logs folder if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create the formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure the file handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join('logs', log_file),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Configure the console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure the logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid log duplication
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger