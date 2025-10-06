"""Telegram message handling utilities"""

import os
import logging
from typing import List
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import MessageLimit

logger = logging.getLogger(__name__)

def split_large_message(text: str, limit: int = MessageLimit.MAX_TEXT_LENGTH) -> List[str]:
    """Split a large message into smaller chunks that fit Telegram's message size limits"""
    if len(text) <= limit:
        return [text]
        
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
            
        # Find the last space within the limit
        split_index = text.rfind(' ', 0, limit)
        if split_index == -1:  # No space found, force split at limit
            split_index = limit
            
        # Add the part and continue with remaining text
        parts.append(text[:split_index])
        text = text[split_index:].lstrip()
        
    return parts

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