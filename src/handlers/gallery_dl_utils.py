"""Gallery-dl integration utilities"""
import os
import subprocess
import json
import logging
from typing import List
from utils.constants import SESSIONS_DIR, COOKIES_FILENAME

logger = logging.getLogger(__name__)

def check_gallery_dl():
    """Verify gallery-dl installation and configuration"""
    try:
        # Check gallery-dl version
        version_cmd = ["gallery-dl", "--version"]
        result = subprocess.run(version_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"gallery-dl version: {result.stdout.strip()}")
        else:
            logger.error(f"gallery-dl check failed: {result.stderr}")
            raise RuntimeError("gallery-dl is not working properly")
            
        # Test cookie access
        cookies_path = os.path.join(SESSIONS_DIR, COOKIES_FILENAME)
        if os.path.exists(cookies_path):
            logger.info(f"Cookie file exists at {cookies_path}")
            with open(cookies_path, 'r') as f:
                content = f.read()
                logger.info(f"Cookie file size: {len(content)} bytes")
        else:
            logger.warning(f"No cookie file found at {cookies_path}")
            
    except FileNotFoundError:
        logger.error("gallery-dl not found in PATH")
        raise RuntimeError("gallery-dl is not installed")
    except Exception as e:
        logger.exception("Error checking gallery-dl")
        raise RuntimeError(f"gallery-dl check failed: {str(e)}")

async def download_instagram_post(url: str, download_path: str) -> List[str]:
    """
    Downloads content from Instagram using gallery-dl.
    Returns a list of downloaded file paths.
    """
    cookies_path = os.path.join(SESSIONS_DIR, COOKIES_FILENAME)
    
    # Ensure download directory exists
    os.makedirs(download_path, exist_ok=True)
    
    # Build the gallery-dl command
    cmd = [
        "gallery-dl",
        "--write-metadata",
        "-D", download_path,
        "--verbose",
        "--config", os.getenv("GALLERY_DL_CFG", "/app/src/utils/gallery-dl.conf")
    ]
    
    # Add cookies if available
    if os.path.exists(cookies_path):
        cmd.extend(["--cookies", cookies_path])
        logger.info("Using Instagram session from cookies.txt")
    else:
        logger.warning("No cookies.txt found, attempting download without authentication")
    
    # Add the URL
    cmd.append(url)
    
    logger.info(f"Running gallery-dl command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    logging.info(f"gallery-dl return code: {result.returncode}")
    logging.info(f"gallery-dl stdout: {result.stdout[:500]}")
    logging.info(f"gallery-dl stderr: {result.stderr[:500]}")
    
    if result.returncode != 0:
        error_msg = result.stderr if result.stderr else result.stdout
        if "login required" in error_msg.lower():
            raise RuntimeError("Login required. Please check if your Instagram session is still valid.")
        elif "not found" in error_msg.lower():
            raise RuntimeError("Content not found. The post may be private or deleted.")
        elif "rate limit" in error_msg.lower():
            raise RuntimeError("Rate limit reached. Please try again later.")
        else:
            raise RuntimeError(f"Download failed: {error_msg}")
            
    if not result.stdout and not result.stderr:
        raise RuntimeError("No output received from gallery-dl. This might indicate a configuration issue.")
    
    # Find all downloaded files
    file_paths = []
    for root, _, files in os.walk(download_path):
        for f in files:
            if not f.endswith((".json", ".txt")):  # Skip metadata files
                file_paths.append(os.path.join(root, f))
                
    if not file_paths:
        logger.warning("No files were downloaded")
        return []
        
    logger.info(f"Successfully downloaded {len(file_paths)} files")
    return file_paths
