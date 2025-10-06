"""
Gallery-dl download resumption utilities.
"""
import os
import json
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

@dataclass
class DownloadState:
    """State information for resuming downloads"""
    bytes_downloaded: int
    total_bytes: Optional[int]
    etag: Optional[str]
    last_modified: Optional[str]

def save_download_state(file_path: str, state: DownloadState) -> None:
    """Save download state to a .state file"""
    state_path = f"{file_path}.state"
    with open(state_path, 'w') as f:
        json.dump({
            'bytes_downloaded': state.bytes_downloaded,
            'total_bytes': state.total_bytes,
            'etag': state.etag,
            'last_modified': state.last_modified
        }, f)

def load_download_state(file_path: str) -> Optional[DownloadState]:
    """Load download state from a .state file"""
    state_path = f"{file_path}.state"
    if not os.path.exists(state_path):
        return None
        
    try:
        with open(state_path, 'r') as f:
            data = json.load(f)
            return DownloadState(
                bytes_downloaded=data['bytes_downloaded'],
                total_bytes=data.get('total_bytes'),
                etag=data.get('etag'),
                last_modified=data.get('last_modified')
            )
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error loading download state: {e}")
        return None

def get_download_range(file_path: str) -> Optional[Tuple[int, Optional[int]]]:
    """
    Get the range to use for resuming download.
    Returns a tuple of (start_byte, end_byte) or None if can't resume.
    """
    state = load_download_state(file_path)
    if not state:
        return None
        
    if not os.path.exists(file_path):
        return None
        
    # Verify the file size matches our state
    actual_size = os.path.getsize(file_path)
    if actual_size != state.bytes_downloaded:
        logger.warning(
            f"File size mismatch for {file_path}: "
            f"expected {state.bytes_downloaded} bytes, got {actual_size}"
        )
        return None
        
    # Return the range for the remaining bytes
    return (actual_size, state.total_bytes)