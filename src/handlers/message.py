import re
import logging
from telegram import Update
from telegram.ext import ContextTypes
from handlers.instagram import download_instagram_content
from utils.constants import INSTAGRAM_URL_PATTERN
from logger import get_logger

logger = get_logger(__name__)

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
            logger.info("Attempting to download content...")
            try:
                await update.message.reply_text("Starting download, please wait...")
                result, file_paths = await download_instagram_content(url)
                await update.message.reply_text(result)
                
                # If we have files, send them
                if file_paths:
                    from handlers.download import send_files
                    await send_files(update, context, file_paths)
            except Exception as e:
                logger.exception("Error in download_instagram_content")
                await update.message.reply_text(f"Download error: {str(e)}")
        # Ignore all other messages
    except Exception as e:
        logger.exception("Error handling message")
        await update.message.reply_text("An error occurred while processing your message.")
