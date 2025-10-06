"""Telegram message handling utilities"""

import os
import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def send_file(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    filepath: str,
    caption: str = None
) -> bool:
    """Send a file through Telegram with proper error handling"""
    try:
        with open(filepath, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(filepath),
                caption=caption
            )
        return True
    except Exception as e:
        logger.exception(f"Error sending file {filepath}")
        await update.message.reply_text(f"Error sending {os.path.basename(filepath)}: {str(e)}")
        return False

async def reply_with_error(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    message: str,
    log_message: str = None
) -> None:
    """Send error message to user and log it"""
    if log_message:
        logger.error(log_message)
    await update.message.reply_text(message)