import os
import logging
from typing import List, Optional, Tuple

# Store the last download info
last_download: Optional[List[str]] = None
logger = logging.getLogger(__name__)

def set_last_download(file_paths: List[str]):
    """Store the paths of the last downloaded files"""
    global last_download
    last_download = file_paths

def get_last_download() -> Optional[List[str]]:
    """Get the paths of the last downloaded files"""
    return last_download

def format_download_info(file_paths: List[str]) -> Tuple[str, float]:
    """Format information about downloaded files"""
    files_info = []
    total_size = 0
    
    for f in file_paths:
        if os.path.exists(f):
            size = os.path.getsize(f)
            size_mb = size / 1024 / 1024
            total_size += size
            files_info.append(f"- {os.path.basename(f)} ({size_mb:.1f}MB)")
            
    files_list = "\n".join(files_info)
    total_size_mb = total_size / 1024 / 1024
    
    message = (
        f"Successfully downloaded {len(file_paths)} file(s) - Total size: {total_size_mb:.1f}MB\n\n"
        f"Files:\n{files_list}\n\n"
        "Use /send_last to receive the downloaded files."
    )
    
    return message, total_size_mb