"""
Handles file upload operations with retry logic and state management.
"""
import os
import logging
import asyncio
from typing import Optional, List, Tuple
import time
from datetime import datetime
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.constants import MessageLimit
from telegram.error import RetryAfter, TimedOut

from utils.state_tracker import StateTracker
from utils.service_manager import service_manager
from utils.constants import JOB_BASE_DIR, MAX_UPLOAD_RETRIES
from utils.telegram_helper import split_large_message
from utils.service_manager import service_manager
from utils.media_info import get_media_info, format_media_info

logger = logging.getLogger(__name__)

class UploadHandler:
    """
    Handles media file uploads to Telegram with state tracking and retry logic.
    """
    def __init__(self, state_tracker: Optional[StateTracker] = None):
        self.state_tracker = state_tracker or service_manager.get(StateTracker)
        self.upload_semaphore = asyncio.Semaphore(2)  # Limit concurrent uploads
        service_manager.register(UploadHandler, self)
        
    async def upload_files(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        job_id: str,
        reply_to_message_id: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Upload all files for a job with retry logic and state tracking.
        Returns tuple of (successful_uploads, failed_uploads).
        """
        try:
            start_time = time.time()
            
            # Get files ready for upload
            files_to_upload = self.state_tracker.prepare_for_upload(job_id)
            if not files_to_upload:
                await update.message.reply_text("No files to upload.")
                return 0, 0

            successful = 0
            failed = 0
            
            # Send initial status message with progress
            from utils.ui_helper import format_job_progress
            
            initial_progress = format_job_progress(
                job_id=job_id,
                downloaded=len(files_to_upload),
                uploaded=0,
                failed=0,
                total=len(files_to_upload)
            )
            
            status_message = await update.message.reply_text(initial_progress)
            
            # Process uploads with concurrency limit
            tasks = []
            for filename in files_to_upload:
                task = asyncio.create_task(
                    self._upload_file_with_retry(
                        update, context, job_id, filename,
                        reply_to_message_id
                    )
                )
                tasks.append(task)
                
            # Wait for all uploads to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                    logger.error(f"Upload failed with error: {str(result)}")
                elif result:
                    successful += 1
                else:
                    failed += 1
                    
            # Update final status with formatted progress
            final_progress = format_job_progress(
                job_id=job_id,
                downloaded=len(files_to_upload),
                uploaded=successful,
                failed=failed,
                total=len(files_to_upload),
                duration=time.time() - start_time if 'start_time' in locals() else None
            )
            
            await status_message.edit_text(final_progress)
            
            # Finalize job state
            self.state_tracker.finalize_job(job_id)
            
            return successful, failed
            
        except Exception as e:
            logger.error(f"Error in upload_files: {str(e)}")
            await update.message.reply_text(
                f"❌ Error during upload process: {str(e)}"
            )
            return 0, 0

    async def _upload_file_with_retry(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        job_id: str,
        filename: str,
        reply_to_message_id: Optional[int] = None,
        retry_count: int = 0
    ) -> bool:
        """
        Upload a single file with retry logic.
        Returns True if successful, False otherwise.
        """
        file_path = os.path.join(JOB_BASE_DIR, job_id, filename)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            self.state_tracker.record_upload(
                job_id, filename, False,
                error="File not found"
            )
            return False
            
        try:
            async with self.upload_semaphore:
                # Determine file type and use appropriate upload method
                file_ext = os.path.splitext(filename)[1].lower()
                
                if file_ext in ['.jpg', '.jpeg', '.png']:
                    # Get media info
                    media_info = get_media_info(file_path)
                    caption = f"{filename}\n\n{format_media_info(media_info)}"
                    
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=open(file_path, 'rb'),
                        reply_to_message_id=reply_to_message_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                elif file_ext in ['.mp4', '.mov']:
                    # Get media info
                    media_info = get_media_info(file_path)
                    caption = f"{filename}\n\n{format_media_info(media_info)}"
                    
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=open(file_path, 'rb'),
                        reply_to_message_id=reply_to_message_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                else:
                    # Get media info
                    media_info = get_media_info(file_path)
                    caption = f"{filename}\n\n{format_media_info(media_info)}"
                    
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=open(file_path, 'rb'),
                        reply_to_message_id=reply_to_message_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                    
                # Record successful upload
                self.state_tracker.record_upload(job_id, filename, True)
                return True
                
        except RetryAfter as e:
            if retry_count < MAX_UPLOAD_RETRIES:
                await asyncio.sleep(e.retry_after)
                return await self._upload_file_with_retry(
                    update, context, job_id, filename,
                    reply_to_message_id, retry_count + 1
                )
            else:
                error_msg = f"Max retries exceeded for {filename}"
                logger.error(error_msg)
                self.state_tracker.record_upload(
                    job_id, filename, False,
                    error=error_msg
                )
                return False
                
        except TimedOut:
            if retry_count < MAX_UPLOAD_RETRIES:
                await asyncio.sleep(5 * (retry_count + 1))  # Exponential backoff
                return await self._upload_file_with_retry(
                    update, context, job_id, filename,
                    reply_to_message_id, retry_count + 1
                )
            else:
                error_msg = f"Upload timed out for {filename}"
                logger.error(error_msg)
                self.state_tracker.record_upload(
                    job_id, filename, False,
                    error=error_msg
                )
                return False
                
        except Exception as e:
            error_msg = f"Error uploading {filename}: {str(e)}"
            logger.error(error_msg)
            self.state_tracker.record_upload(
                job_id, filename, False,
                error=error_msg
            )
            return False

    async def get_upload_status(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        job_id: str
    ) -> None:
        """Send current upload status for a job"""
        try:
            summary = self.state_tracker.get_job_summary(job_id)
            
            status_text = (
                f"📊 Upload Status for Job {job_id}:\n\n"
                f"Status: {summary['status']}\n"
                f"Total Files: {summary['stats']['total_files']}\n"
                f"✅ Uploaded: {summary['stats']['uploaded']}\n"
                f"❌ Failed: {summary['stats']['failed']}\n"
                f"⏳ Pending: {summary['stats']['pending']}\n"
                f"📤 Uploading: {summary['stats']['uploading']}\n"
                f"⏱️ Duration: {summary['duration']:.1f}s"
            )
            
            if summary['error']:
                status_text += f"\n\n❗ Error: {summary['error']}"
                
            await update.message.reply_text(status_text)
            
        except Exception as e:
            logger.error(f"Error getting upload status: {str(e)}")
            await update.message.reply_text(
                f"❌ Error getting upload status: {str(e)}"
            )