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
            
            # Send initial status message that we'll update
            from utils.ui_helper import format_job_progress
            status_msg = await update.message.reply_text(
                format_job_progress(
                    job_id=job_id,
                    downloaded=len(files_to_upload),
                    uploaded=0,
                    failed=0,
                    total=len(files_to_upload),
                    duration=0,
                    is_complete=False,
                    status_override="⏳ Preparing upload..."
                )
            )
            
            last_update = time.time()
            UPDATE_INTERVAL = 15  # Update every 15 seconds
            
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
                
                # Update status message periodically
                now = time.time()
                if now - last_update >= UPDATE_INTERVAL:
                    progress = format_job_progress(
                        job_id=job_id,
                        downloaded=len(files_to_upload),
                        uploaded=successful,
                        failed=failed,
                        total=len(files_to_upload),
                        duration=now - start_time,
                        is_complete=False,
                        status_override=f"⏬ Uploading {successful + 1}/{len(files_to_upload)} files"
                    )
                    try:
                        await context.bot.edit_message_text(
                            chat_id=update.effective_chat.id,
                            message_id=status_msg.message_id,
                            text=progress
                        )
                        last_update = now
                    except Exception as e:
                        logger.warning(f"Failed to update status message: {e}")

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
                    
            # Calculate duration and update final status
            duration = time.time() - start_time
            
            # Update status message with final results
            final_progress = format_job_progress(
                job_id=job_id,
                downloaded=len(files_to_upload),
                uploaded=successful,
                failed=failed,
                total=len(files_to_upload),
                duration=duration,
                is_complete=True
            )
            
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=final_progress
                )
            except Exception as e:
                logger.warning(f"Failed to update final status: {e}")
                # If edit fails, send as new message
                await update.message.reply_text(final_progress)
            
            # Finalize job state with duration
            self.state_tracker.finalize_job(
                job_id,
                duration=duration,
                suppress_status=True  # Don't show additional status message
            )
            
            # Note: We don't need to show get_upload_status here since we have the final report
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
                
                # Get list of all files in job
                files_in_job = self.state_tracker.get_job_files(job_id)
                total_media = len(files_in_job) if files_in_job else None

                # Get media number if possible
                media_number = None
                if total_media and files_in_job and filename in files_in_job:
                    try:
                        media_number = files_in_job.index(filename) + 1
                        total_media = len(files_in_job)
                    except (ValueError, TypeError):
                        pass  # Skip if we can't determine the position

                # Get media info
                media_info = get_media_info(file_path)
                caption = format_media_info(media_info, media_number, total_media)

                if file_ext in ['.jpg', '.jpeg', '.png']:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=open(file_path, 'rb'),
                        reply_to_message_id=reply_to_message_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                elif file_ext in ['.mp4', '.mov']:
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=open(file_path, 'rb'),
                        reply_to_message_id=reply_to_message_id,
                        caption=caption,
                        parse_mode='HTML'
                    )
                else:
                        # Get media info (avoid duplicate call)
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