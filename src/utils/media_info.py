"""
Utilities for extracting and formatting media information.
"""
import os
import json
import logging
from typing import Dict, Optional
import humanize

logger = logging.getLogger(__name__)

def get_media_info(file_path: str) -> Dict:
    """
    Get detailed information about a media file and its metadata.
    Returns a dictionary with file details and Instagram metadata if available.
    """
    try:
        file_stats = os.stat(file_path)
        file_size = humanize.naturalsize(file_stats.st_size)
        
        # Basic file info
        info = {
            'size': file_size,
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

def format_media_info(info: Dict) -> str:
    """Format media information into a user-friendly string."""
    lines = []
    
    try:
        # Basic file info
        if 'size' in info:
            lines.append(f"📦 Size: {info['size']}")
        
        # Resolution if available
        if 'width' in info and 'height' in info and info['width'] and info['height']:
            lines.append(f"🖼️ Resolution: {info['width']}x{info['height']}")
        
        # Instagram metadata if available
        if 'likes' in info and info['likes']:
            try:
                likes = humanize.intcomma(info['likes'])
                lines.append(f"❤️ Likes: {likes}")
            except:
                pass
                
        if 'username' in info and info['username']:
            lines.append(f"👤 From: @{info['username']}")
            
        if 'date' in info and info['date']:
            lines.append(f"📅 Posted: {info['date']}")
            
        if 'description' in info and info['description']:
            caption = str(info['description'])
            if len(caption) > 50:
                caption = caption[:47] + "..."
            lines.append(f"📝 Caption: {caption}")
        
        return "\n".join(lines) if lines else "No media info available"
    except Exception as e:
        logger.error(f"Error formatting media info: {str(e)}")
        return "Error formatting media info"