"""
Utilities for generating and standardizing file names.
"""
import re
from datetime import datetime
from typing import Tuple

def generate_filename(username: str, post_id: str, index: int, total: int, ext: str) -> str:
    """
    Generate a standardized filename following the pattern:
    {username}{post_date}{post_id}_{media_index}of{total}.{ext}
    """
    current_date = datetime.now().strftime("%Y%m%d")
    # Sanitize username and post_id
    username = re.sub(r'[^\w\-]', '_', username)
    post_id = re.sub(r'[^\w\-]', '_', post_id)
    
    return f"{username}_{current_date}_{post_id}_{index}of{total}.{ext}"
    
def parse_filename(filename: str) -> Tuple[str, str, str, int, int]:
    """
    Parse a filename back into its components.
    Returns (username, date, post_id, index, total)
    """
    pattern = r"(\w+)_(\d{8})_(\w+)_(\d+)of(\d+)\.\w+"
    match = re.match(pattern, filename)
    
    if not match:
        raise ValueError(f"Invalid filename format: {filename}")
        
    username, date, post_id, index, total = match.groups()
    return username, date, post_id, int(index), int(total)
    
def validate_filename(filename: str) -> bool:
    """Check if a filename follows the standardized pattern"""
    try:
        parse_filename(filename)
        return True
    except ValueError:
        return False