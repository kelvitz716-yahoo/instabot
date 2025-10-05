import os
import logging
from typing import List
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from handlers.instagram import download_instagram_content
from handlers.downloader import get_last_download

logger = logging.getLogger(__name__)

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /download command"""
    if not context.args:
        await update.message.reply_text("Please provide an Instagram URL. Usage: /download <url>")
        return
    url = context.args[0]
    result = download_instagram_content(url)
    await update.message.reply_text(result)

async def send_last_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the last downloaded files to the user"""
    last_download = get_last_download()
    
    if not last_download:
        await update.message.reply_text("No recent downloads available. Download something first!")
        return
        
    await update.message.reply_text("Sending your files...")
    
    for filepath in last_download:
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            continue
            
        try:
            # Get file size
            size_mb = os.path.getsize(filepath) / 1024 / 1024
            
            # Send with appropriate method based on size
            if size_mb > 50:  # Telegram's bot API limit for regular files
                await update.message.reply_text(
                    f"File {os.path.basename(filepath)} is too large ({size_mb:.1f}MB) for direct sending. "
                    "Consider splitting into smaller parts or using a different delivery method."
                )
            else:
                with open(filepath, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=os.path.basename(filepath),
                        caption=f"Size: {size_mb:.1f}MB"
                    )
        except Exception as e:
            logger.exception(f"Error sending file {filepath}")
            await update.message.reply_text(f"Error sending {os.path.basename(filepath)}: {str(e)}")

def set_last_download(file_paths: List[str]):
    """Store the paths of the last downloaded files"""
    global last_download
    last_download = file_paths

def get_download_handlers():
    return [
        CommandHandler("download", download),
        CommandHandler("send_last", send_last_download)
    ]
