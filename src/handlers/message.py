import re
import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.constants import INSTAGRAM_URL_PATTERN
from handlers.download import DownloadHandler
from utils.service_manager import service_manager
from logger import get_logger

logger = get_logger(__name__)

# Get handler from service manager
download_handler = service_manager.get(DownloadHandler)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message.text or ""
        # If it's a command, ignore (handled elsewhere)
        if message.startswith("/"):
            return
            
        # Detect Instagram URL
        match = INSTAGRAM_URL_PATTERN.search(message)
        if match:
            url = match.group(0)
            logger.info(f"Detected Instagram URL: {url}")
            
            # Process with download handler - this will handle both download and upload
            await download_handler.handle_download(
                update,
                context,
                url,
                update.message.message_id  # For reply chain
            )
        # Ignore all other messages
    except Exception as e:
        logger.exception("Error handling message")
        await update.message.reply_text("An error occurred while processing your message.")
