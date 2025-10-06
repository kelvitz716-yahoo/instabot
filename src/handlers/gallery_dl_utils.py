import os
import tempfile
import subprocess
import json
import logging
from typing import Tuple, List

def check_gallery_dl():
    """Verify gallery-dl installation and configuration"""
    logger = logging.getLogger(__name__)
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
        cookies_path = "/app/sessions/cookies.txt"
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

def run_gallery_dl(url: str) -> Tuple[str, List[str], List[str], str]:
    """
    Downloads content from Instagram using gallery-dl to a temp directory.
    Returns (download_dir, file_paths, captions, stats_json)
    """
    logger = logging.getLogger(__name__)
    temp_dir = tempfile.mkdtemp(prefix="gallerydl_")
    cookies_path = "/app/sessions/cookies.txt"
    
    # Build the gallery-dl command
    cmd = [
        "gallery-dl",
        "--write-metadata",
        "-D", temp_dir,
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
    
    # Parse JSON output for stats
    stats_json = result.stdout
    # Find all downloaded files
    file_paths = []
    captions = []
    for root, _, files in os.walk(temp_dir):
        for f in files:
            if f.endswith(".json"):
                # Try to extract caption from metadata
                try:
                    with open(os.path.join(root, f), "r") as meta:
                        meta_json = json.load(meta)
                        if "caption" in meta_json:
                            captions.append(meta_json["caption"])
                except Exception:
                    pass
            elif not f.endswith(".txt"):
                file_paths.append(os.path.join(root, f))
    return temp_dir, file_paths, captions, stats_json
