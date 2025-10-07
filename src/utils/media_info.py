"""
Utilities for extracting and formatting media information.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
import humanize
from utils.ui_helper import format_bytes

logger = logging.getLogger(__name__)

def format_media_info(media_info: Dict[str, Any], media_number: Optional[int] = None, total_media: Optional[int] = None) -> str:
    """Format media information into readable string"""
    if not media_info:
        return "No media information available"

    resolution = f"{media_info.get('width', 0)}x{media_info.get('height', 0)}"
    size = format_bytes(media_info.get('size', 0))
    duration = media_info.get('duration')

    info = []
    
    # Show media number if provided
    if isinstance(media_number, (int, str)) and isinstance(total_media, (int, str)):
        try:
            media_number = int(str(media_number))
            total_media = int(str(total_media))
            info.append(f"📎 Media {media_number}/{total_media}")
        except (ValueError, TypeError):
            pass  # Skip media numbering if conversion fails
    
    info.append(f"📦 Size: {size}")
    
    if resolution != "0x0":
        info.append(f"🖼️ Resolution: {resolution}")
        
    if duration:
        info.append(f"⏱️ Duration: {duration:.1f}s")

    return "\n".join(info)

def get_media_info(file_path: str) -> Dict:
    """
    Get detailed information about a media file and its metadata.
    Returns a dictionary with file details and Instagram metadata if available.
    """
    try:
        file_stats = os.stat(file_path)
        
        # Basic file info
        info = {
            'size': file_stats.st_size,  # Raw size in bytes
            'filename': os.path.basename(file_path),
            'last_modified': file_stats.st_mtime
        }
        
        # Try to get Instagram metadata if available
        json_path = f"{file_path}.json"
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                metadata = json.load(f)
                info.update({
                    'width': metadata.get('width'),
                    'height': metadata.get('height'),
                    'likes': metadata.get('likes'),
                    'description': metadata.get('description'),
                    'username': metadata.get('username'),
                    'date': metadata.get('date')
                })
        
        return info
    except Exception as e:
        return {'error': str(e)}

