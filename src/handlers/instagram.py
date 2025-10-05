import re
import os
import logging
from typing import Union
from utils.constants import (
    COOKIES_PATH, INSTAGRAM_URL_PATTERN,
    MSG_INVALID_URL, MSG_NO_SESSION, MSG_NO_CONTENT,
    MSG_DOWNLOAD_SUCCESS
)
from utils.file_handler import format_file_list
from handlers.gallery_dl_utils import run_gallery_dl, check_gallery_dl
logger = logging.getLogger(__name__)

def download_instagram_content(url: str) -> str:
    """
    Download Instagram content using gallery-dl.
    Returns a message describing the download result.
    """
    try:
        # Verify URL format
        if not re.match(INSTAGRAM_URL_PATTERN, url):
            return MSG_INVALID_URL
            
        logger.info(f"Starting download for URL: {url}")
        
        # Check for required session file
        if not os.path.exists(COOKIES_PATH):
            return MSG_NO_SESSION
            
        # Verify gallery-dl is working
        try:
            check_gallery_dl()
        except Exception as e:
            logger.error(f"gallery-dl check failed: {str(e)}")
            return f"System error: {str(e)}"

        # Try the download
        try:
            logger.info("Starting gallery-dl download...")
            temp_dir, file_paths, captions, stats = run_gallery_dl(url)
            if not file_paths:
                return MSG_NO_CONTENT
                
            # Store downloaded files and format message
            from handlers.download import set_last_download
            set_last_download(file_paths)
            
            files_list, total_size_mb = format_file_list(file_paths)
            return MSG_DOWNLOAD_SUCCESS.format(
                count=len(file_paths),
                size=total_size_mb,
                files=files_list
            )
            
        except RuntimeError as e:
            logger.error(f"gallery-dl error for {url}: {str(e)}")
            return f"Error: {str(e)}"
            
    except Exception as e:
        logger.exception(f"Unexpected error downloading {url}")
        return f"An unexpected error occurred: {str(e)}"
# End of file
