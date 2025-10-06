import os
import logging
from typing import List
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.constants import (
    MAX_TELEGRAM_FILE_SIZE, MSG_NO_DOWNLOADS,
    MSG_SENDING_FILES, MSG_FILE_TOO_LARGE,
    MSG_NO_URL
)
from utils.telegram_helper import reply_with_error, send_file
from handlers.instagram import download_instagram_content

logger = logging.getLogger(__name__)

async def send_files(update: Update, context: ContextTypes.DEFAULT_TYPE, file_paths: List[str]) -> None:
    """Send files to user with progress updates"""
    if not file_paths:
        return
        
    await update.message.reply_text(MSG_SENDING_FILES)
    
    for i, filepath in enumerate(file_paths, 1):
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            continue
            
        try:
            size_mb = os.path.getsize(filepath) / 1024 / 1024
            if size_mb > MAX_TELEGRAM_FILE_SIZE / 1024 / 1024:
                await reply_with_error(
                    update, context,
                    MSG_FILE_TOO_LARGE.format(
                        filename=os.path.basename(filepath),
                        size=size_mb
                    )
                )
            else:
                # Add progress information
                progress = f"Sending file {i}/{len(file_paths)}"
                await send_file(
                    update, context,
                    filepath,
                    caption=f"{progress}\nSize: {size_mb:.1f}MB"
                )
        except Exception as e:
            logger.exception(f"Error sending file {filepath}")
            await reply_with_error(
                update, context,
                f"Error sending {os.path.basename(filepath)}: {str(e)}"
            )
    
    await update.message.reply_text("All files have been sent!")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /download command"""
    if not context.args:
        await reply_with_error(update, context, MSG_NO_URL)
        return
    
    url = context.args[0]
    await update.message.reply_text("Starting download, please wait...")
    result, file_paths = await download_instagram_content(url)
    await update.message.reply_text(result)
    
    if file_paths:  # If we have files, send them immediately
        await send_files(update, context, file_paths)

def get_download_handlers():
    """Get all download-related command handlers"""
    return [
        CommandHandler("download", handle_download)
    ]