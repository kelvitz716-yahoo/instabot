import os
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

def ensure_dir(path: str) -> None:
    """Ensure directory exists, create if not"""
    os.makedirs(path, exist_ok=True)

def get_file_info(filepath: str) -> Tuple[str, float]:
    """Get file name and size in MB"""
    size_bytes = os.path.getsize(filepath)
    size_mb = size_bytes / 1024 / 1024
    return os.path.basename(filepath), size_mb

def format_file_list(files: List[str]) -> Tuple[str, float]:
    """Format a list of files with their sizes"""
    files_info = []
    total_size = 0
    
    for f in files:
        if os.path.exists(f):
            name, size_mb = get_file_info(f)
            total_size += size_mb * 1024 * 1024  # Convert back to bytes for total
            files_info.append(f"- {name} ({size_mb:.1f}MB)")
    
    files_list = "\n".join(files_info)
    total_size_mb = total_size / 1024 / 1024
    
    return files_list, total_size_mb

def validate_file_content(filepath: str, required_strings: List[str]) -> Tuple[bool, Optional[str]]:
    """Validate file exists and contains required strings"""
    if not os.path.exists(filepath):
        return False, "File does not exist"
        
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if not content.strip():
                return False, "File is empty"
            
            missing = [s for s in required_strings if s not in content]
            if missing:
                return False, f"Missing required content: {', '.join(missing)}"
                
            return True, None
    except Exception as e:
        return False, f"Error reading file: {str(e)}"