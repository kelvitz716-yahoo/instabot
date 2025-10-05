import logging
import sys
from typing import Optional

def setup_logging(level: int = logging.INFO) -> None:
    """
    Set up application-wide logging configuration.
    Args:
        level: The logging level to use (default: INFO)
    """
    # Create formatter
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Configure stream handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(stream_handler)
    
    # Set more restrictive levels for some chatty libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with the given name.
    Args:
        name: The logger name (default: None, returns root logger)
    Returns:
        A Logger instance
    """
    return logging.getLogger(name)
