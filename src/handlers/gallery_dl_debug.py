import subprocess
import os
import logging

logger = logging.getLogger(__name__)

def debug_gallery_dl(url: str) -> str:
    """
    Run gallery-dl in debug mode with enhanced logging and environment details.
    
    Args:
        url: The Instagram URL to download from
        
    Returns:
        Detailed debug information including command output and environment context
    """
    # Log environment details
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"PATH: {os.environ.get('PATH', 'Not set')}")
    
    # Check if gallery-dl is available
    try:
        version_cmd = ["gallery-dl", "--version"]
        version = subprocess.run(version_cmd, capture_output=True, text=True)
        logger.info(f"gallery-dl version: {version.stdout.strip()}")
    except FileNotFoundError:
        logger.error("gallery-dl not found in PATH")
        return "ERROR: gallery-dl not found in PATH"

    # Run with maximum verbosity for debugging
    cmd = ["gallery-dl", "--verbose", "--debug", url]
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Log full output for debugging
        if result.stdout:
            logger.debug(f"gallery-dl stdout:\n{result.stdout}")
        if result.stderr:
            logger.debug(f"gallery-dl stderr:\n{result.stderr}")
        logger.info(f"gallery-dl return code: {result.returncode}")
        
        # Return formatted debug info
        debug_info = [
            "=== Gallery-DL Debug Information ===",
            f"Return Code: {result.returncode}",
            "\n=== Standard Output ===",
            result.stdout if result.stdout else "No output",
            "\n=== Error Output ===",
            result.stderr if result.stderr else "No errors",
            "\n=== Environment ===",
            f"CWD: {os.getcwd()}",
            f"gallery-dl version: {version.stdout.strip()}",
        ]
        return "\n".join(debug_info)
        
    except Exception as e:
        error_msg = f"Failed to run gallery-dl: {str(e)}"
        logger.error(error_msg)
        return error_msg
