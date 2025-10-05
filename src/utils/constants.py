"""Shared constants and configuration"""

import os

# File paths
SESSIONS_DIR = "/app/sessions"
COOKIES_FILENAME = "cookies.txt"
COOKIES_PATH = os.path.join(SESSIONS_DIR, COOKIES_FILENAME)

# Instagram related
INSTAGRAM_URL_PATTERN = r"https?://(www\.)?instagram\.com/[\w\-./?=&%]+"
REQUIRED_COOKIE_STRINGS = ["sessionid", "ds_user_id", "instagram.com"]

# Telegram limits
MAX_TELEGRAM_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Message templates
MSG_NO_DOWNLOADS = "No recent downloads available. Download something first!"
MSG_SENDING_FILES = "Sending your files..."
MSG_FILE_TOO_LARGE = (
    "File {filename} is too large ({size:.1f}MB) for direct sending. "
    "Consider splitting into smaller parts or using a different delivery method."
)
MSG_DOWNLOAD_SUCCESS = (
    "Successfully downloaded {count} file(s) - Total size: {size:.1f}MB\n\n"
    "Files:\n{files}\n\n"
    "Use /send_last to receive the downloaded files."
)
MSG_NO_URL = "Please provide an Instagram URL. Usage: /download <url>"
MSG_INVALID_URL = "Error: Not a valid Instagram URL. Please provide a link from instagram.com"
MSG_NO_SESSION = "Error: No active Instagram session. Please use /session_load to upload your cookies.txt first."
MSG_NO_CONTENT = "Error: No content was downloaded. The post might be private or deleted."

# Help messages
HELP_SESSION_LOAD = (
    "Please upload your Instagram cookies.txt file.\n"
    "Instructions: Export your Instagram cookies using the browser extension 'Get cookies.txt' "
    "and upload the file here."
)