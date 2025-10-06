import os
import logging
import asyncio
from typing import Optional, List
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.constants import (
    MAX_TELEGRAM_FILE_SIZE, MSG_NO_DOWNLOADS,
    MSG_SENDING_FILES, MSG_FILE_TOO_LARGE,
    MSG_NO_URL, JOB_BASE_DIR
)
from utils.telegram_helper import reply_with_error
from utils.state_tracker import StateTracker
from utils.service_manager import service_manager
from handlers.upload import UploadHandler
from utils.instagram_validator import is_valid_instagram_url
from handlers.gallery_dl_utils import download_instagram_post
from utils.service_manager import service_manager

logger = logging.getLogger(__name__)

class DownloadHandler:
    """
    Handles downloading media from Instagram with state tracking and retry logic.
    """
    def __init__(self, state_tracker: Optional[StateTracker] = None, upload_handler: Optional[UploadHandler] = None):
        self.state_tracker = state_tracker or service_manager.get(StateTracker)
        self.upload_handler = upload_handler or service_manager.get(UploadHandler)
        self.download_semaphore = asyncio.Semaphore(2)  # Limit concurrent downloads
        service_manager.register(DownloadHandler, self)
        
    async def handle_download(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        url: Optional[str] = None,
        reply_to_message_id: Optional[int] = None
    ) -> None:
        """
        Handle download request with state tracking and automatic upload.
        """
        try:
            if not url and context.args:
                url = context.args[0]
            
            if not url:
                await reply_with_error(update, context, MSG_NO_URL)
                return
                
            if not is_valid_instagram_url(url):
                await update.message.reply_text(
                    "❌ Invalid Instagram URL. Please provide a valid Instagram post URL."
                )
                return
                
            # Initialize download job
            job_id = self.state_tracker.initialize_download_job(url)
            
            # Initial status message
            initial_msg = (
                f"🔗 Processing Instagram URL\n"
                f"══════════════════════\n"
                f"Job ID: {job_id}\n"
                f"URL: {url}\n\n"
                f"⏳ Initializing download..."
            )
            status_message = await update.message.reply_text(initial_msg)
            
            # Start download process
            download_path = os.path.join(JOB_BASE_DIR, job_id)
            os.makedirs(download_path, exist_ok=True)
            
            # Download files
            downloaded_files = await download_instagram_post(url, download_path)
            
            if not downloaded_files:
                await status_message.edit_text("❌ No files were downloaded.")
                self.state_tracker.finalize_job(job_id)
                return
                
            # Record downloads in state tracker
            total_files = len(downloaded_files)
            processed_files = 0
            total_bytes = 0
            
            for filename in downloaded_files:
                file_path = os.path.join(download_path, filename)
                file_size = os.path.getsize(file_path)
                total_bytes += file_size
                processed_files += 1
                
                # Record download with size info
                self.state_tracker.record_download(job_id, filename, url, file_size)
                
                # Update progress
                self.state_tracker.update_job_heartbeat(
                    job_id,
                    files_processed=processed_files,
                    total_files=total_files,
                    current_operation=f"Downloading {filename}",
                    bytes_processed=total_bytes
                )
                
            from utils.ui_helper import format_job_progress
            
            complete_msg = format_job_progress(
                job_id=job_id,
                downloaded=len(downloaded_files),
                uploaded=0,
                failed=0,
                total=len(downloaded_files)
            )
            
            await status_message.edit_text(
                complete_msg + "\n\n🔄 Initiating upload process..."
            )
            
            # Start upload process
            successful, failed = await self.upload_handler.upload_files(
                update, context, job_id, reply_to_message_id
            )
            
            if successful + failed > 0:
                await self.upload_handler.get_upload_status(
                    update, context, job_id
                )
                
        except Exception as e:
            error_msg = f"Error processing download: {str(e)}"
            logger.error(error_msg)
            await update.message.reply_text(f"❌ {error_msg}")
            
    async def get_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        job_id: str
    ) -> None:
        """Get status of a specific job"""
        await self.upload_handler.get_upload_status(
            update, context, job_id
        )

def get_download_handlers():
    """Get all download-related command handlers"""
    download_handler = DownloadHandler()
    return [
        CommandHandler("download", download_handler.handle_download)
    ]