import re
import os
from handlers.gallery_dl_utils import run_gallery_dl, check_gallery_dl
from handlers.downloader import set_last_download, format_download_info
from handlers.gallery_dl_debug import debug_gallery_dl
def download_instagram_content(url: str) -> str:
    """
    Download Instagram content using gallery-dl, return path, count, and size info.
    Returns detailed debug information for troubleshooting.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Verify URL format
        if "instagram.com" not in url:
            return "Error: Not a valid Instagram URL. Please provide a link from instagram.com"
            
        logger.info(f"Starting download for URL: {url}")
        
        # Check for required session file
        session_path = "/app/sessions/cookies.txt"
        if not os.path.exists(session_path):
            return "Error: No active Instagram session. Please use /session_load to upload your cookies.txt first."
            
        # Verify gallery-dl is working
        try:
            check_gallery_dl()
        except Exception as e:
            logger.error(f"gallery-dl check failed: {str(e)}")
            return f"System error: {str(e)}"

        # Try the download with proper error handling
        try:
            logger.info("Starting gallery-dl download...")
            temp_dir, file_paths, captions, stats = run_gallery_dl(url)
            if not file_paths:
                return "Error: No content was downloaded. The post might be private or deleted."

            # Store the downloaded files for later sending
            set_last_download(file_paths)
            
            # Format info about the downloaded files
            message, _ = format_download_info(file_paths)
            return message
            
        except RuntimeError as e:
            logger.error(f"gallery-dl error for {url}: {str(e)}")
            return f"Error: {str(e)}"
            
    except Exception as e:
        logger.exception(f"Unexpected error downloading {url}")
        return f"An unexpected error occurred: {str(e)}"
# End of file
