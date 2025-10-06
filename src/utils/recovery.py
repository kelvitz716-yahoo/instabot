"""
Recovery system for handling interrupted jobs and crash recovery.
"""
import os
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from .job_manager import JobManager, JobState, JobStatus, FileStatus
from .service_manager import service_manager
from .reporting import ReportingSystem
from handlers.gallery_dl_utils import download_instagram_post

logger = logging.getLogger(__name__)

class RecoverySystem:
    """
    Handles crash recovery and job resumption functionality.
    """
    def __init__(
        self, 
        job_manager: JobManager,
        reporting_system: Optional['ReportingSystem'] = None
    ):
        if not job_manager:
            raise ValueError("JobManager is required for RecoverySystem")
            
        self.job_manager = job_manager
        self.max_job_age = timedelta(days=7)  # Don't try to recover jobs older than this
        self.inactive_timeout = timedelta(hours=1)  # Consider a job stuck if no updates for this long
        
        # Wait to get reporting system until it's registered
        self.reporting = reporting_system
        if not reporting_system:
            try:
                self.reporting = service_manager.get(ReportingSystem)
            except:
                # Will get set later via set_reporting_system
                pass
                
        service_manager.register(RecoverySystem, self)
        
    def set_reporting_system(self, reporting_system: 'ReportingSystem'):
        """Set the reporting system after it's available."""
        self.reporting = reporting_system

    async def scan_for_interrupted_jobs(self) -> List[JobState]:
        """
        Scan for jobs that were interrupted by a crash or unexpected shutdown.
        Returns a list of JobState objects for interrupted jobs.
        """
        interrupted_jobs = []
        now = datetime.now()

        for job_id in self._get_active_job_ids():
            job_state = self.job_manager.get_job_state(job_id)
            if not job_state:
                continue

            # Skip old jobs
            job_start = datetime.fromtimestamp(job_state.start_time)
            if now - job_start > self.max_job_age:
                continue

            # Check if job was interrupted
            if job_state.status in [JobStatus.DOWNLOADING, JobStatus.UPLOADING]:
                last_update = self._get_last_update_time(job_state)
                if now - last_update > self.inactive_timeout:
                    msg = f"🔎 Found interrupted job: {job_id}\nLast update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}"
                    logger.info(msg)
                    self.reporting.send_notification(msg)
                    interrupted_jobs.append(job_state)

        if interrupted_jobs:
            summary = f"📊 Recovery scan complete:\nFound {len(interrupted_jobs)} interrupted job(s)"
            self.reporting.send_notification(summary)

        return interrupted_jobs

    async def resume_job(self, job_state: JobState) -> bool:
        """
        Attempt to resume an interrupted job from its last known good state.
        
        Args:
            job_state: The state of the job to resume
            
        Returns:
            bool: True if job was successfully resumed, False otherwise
        """
        try:
            # Mark job as recovering
            self.job_manager.update_job_state(job_state.job_id, status=JobStatus.RECOVERING)
            msg = f"🔄 Starting recovery for job {job_state.job_id}"
            logger.info(msg)
            self.reporting.send_notification(msg)
            
            # Check each file's status and resume accordingly
            files_to_retry = []
            for filename, file_state in job_state.files.items():
                if file_state.status in [FileStatus.DOWNLOADING, FileStatus.UPLOADING]:
                    if file_state.retries < 3:  # Allow up to 3 retries
                        files_to_retry.append((filename, file_state))
                    else:
                        file_state.status = FileStatus.FAILED
                        file_state.error = "Max retries exceeded during recovery"
                        err_msg = f"❌ {filename}: Max retries exceeded during recovery"
                        logger.warning(err_msg)
                        self.reporting.send_notification(err_msg)

            if not files_to_retry:
                msg = f"❌ No files eligible for retry in job {job_state.job_id}"
                logger.info(msg)
                self.reporting.send_notification(msg)
                self.job_manager.update_job_state(job_state.job_id, status=JobStatus.FAILED)
                return False

            # Retry eligible files
            status_msg = f"📝 Recovery plan for job {job_state.job_id}:\n"
            status_msg += f"Total files to retry: {len(files_to_retry)}"
            self.reporting.send_notification(status_msg)

            for filename, file_state in files_to_retry:
                if file_state.status == FileStatus.DOWNLOADING:
                    msg = f"⬇️ Resuming download for {filename}"
                    logger.info(msg)
                    self.reporting.send_notification(msg)
                    await self._resume_download(job_state.job_id, filename, file_state)
                elif file_state.status == FileStatus.UPLOADING:
                    msg = f"⬆️ Resuming upload for {filename}"
                    logger.info(msg)
                    self.reporting.send_notification(msg)
                    self._resume_upload(job_state.job_id, filename, file_state)
            
            # Update job status based on progress
            self._update_job_status_after_recovery(job_state)
            
            success_msg = f"✅ Recovery completed for job {job_state.job_id}"
            self.reporting.send_notification(success_msg)
            return True
            
        except Exception as e:
            error_msg = f"❌ Failed to resume job {job_state.job_id}:\n{str(e)}"
            logger.error(error_msg)
            self.reporting.send_notification(error_msg)
            self.job_manager.update_job_state(
                job_state.job_id,
                status=JobStatus.FAILED,
                error=f"Recovery failed: {str(e)}"
            )
            return False

    async def _resume_download(self, job_id: str, filename: str, file_state: FileStatus) -> None:
        """Resume a partially downloaded file"""
        file_path = os.path.join(self.job_manager.base_path, job_id, "media", filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Cannot resume download - file not found: {file_path}")
            
        # Update state to downloading
        self.job_manager.update_job_state(job_id, status=JobStatus.DOWNLOADING)
        
        # Call gallery-dl to resume download
        try:
            download_path = os.path.join(self.job_manager.base_path, job_id, "media")
            downloaded_files = await download_instagram_post(
                file_state.original_url, 
                download_path
            )
            
            # Update file state on successful resume
            if downloaded_files:
                file_state.status = FileStatus.DOWNLOADED
                file_state.download_time = time.time()
                logger.info(f"Successfully resumed download for {filename}")
            else:
                raise RuntimeError("No files were downloaded during recovery attempt")
            
        except Exception as e:
            error_msg = f"❌ Failed to resume download for {filename}:\n{str(e)}"
            logger.error(error_msg)
            self.reporting.send_notification(error_msg)
            file_state.status = FileStatus.FAILED
            file_state.error = str(e)
            raise

    def _resume_upload(self, job_id: str, filename: str, file_state: FileStatus) -> None:
        """Resume a failed or interrupted upload"""
        file_path = os.path.join(self.job_manager.base_path, job_id, "media", filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Cannot resume upload - file not found: {file_path}")
            
        # Add the file back to the upload queue
        self.job_manager.add_file_to_job(job_id, filename, file_state.original_url)
        
    def _update_job_status_after_recovery(self, job_state: JobState) -> None:
        """Update job status based on the state of its files after recovery"""
        all_completed = True
        has_failures = False
        failed_count = 0
        completed_count = 0
        pending_count = 0
        
        for file_state in job_state.files.values():
            if file_state.status == FileStatus.UPLOADED:
                completed_count += 1
            elif file_state.status == FileStatus.FAILED:
                has_failures = True
                all_completed = False
                failed_count += 1
            else:
                all_completed = False
                pending_count += 1
                
        status_msg = f"📊 Recovery Status for job {job_state.job_id}:\n"
        status_msg += f"✅ Completed: {completed_count}\n"
        status_msg += f"❌ Failed: {failed_count}\n"
        status_msg += f"⏳ Pending: {pending_count}"
        
        self.reporting.send_notification(status_msg)
                
        if all_completed:
            msg = f"✨ Job {job_state.job_id} recovery completed successfully"
            self.job_manager.update_job_state(job_state.job_id, status=JobStatus.COMPLETED)
            self.reporting.send_notification(msg)
        elif has_failures:
            msg = f"❌ Job {job_state.job_id} recovery completed with failures"
            self.job_manager.update_job_state(job_state.job_id, status=JobStatus.FAILED)
            self.reporting.send_notification(msg)
        else:
            # Some files still need processing
            msg = f"⏳ Job {job_state.job_id} partially recovered - some files still need processing"
            self.job_manager.update_job_state(job_state.job_id, status=JobStatus.INTERRUPTED)
            self.reporting.send_notification(msg)
            
    def _get_active_job_ids(self) -> List[str]:
        """Get list of job IDs in the jobs directory."""
        try:
            jobs_dir = os.path.join(self.job_manager.base_path, "jobs")
            return [d for d in os.listdir(jobs_dir)
                   if os.path.isdir(os.path.join(jobs_dir, d))]
        except Exception as e:
            logger.error(f"Error scanning jobs directory: {str(e)}")
            return []
                
    def _get_last_update_time(self, job_state: JobState) -> datetime:
        """Get the timestamp of the last update to this job"""
        # Check for heartbeat first
        if hasattr(job_state, 'last_heartbeat') and job_state.last_heartbeat:
            return datetime.fromtimestamp(job_state.last_heartbeat)
            
        # Fall back to checking file timestamps
        latest_time = datetime.fromtimestamp(job_state.start_time)
        for file_state in job_state.files.values():
            if file_state.download_time:
                time = datetime.fromtimestamp(file_state.download_time)
                if time > latest_time:
                    latest_time = time
            if file_state.upload_time:
                time = datetime.fromtimestamp(file_state.upload_time)
                if time > latest_time:
                    latest_time = time
                    
        return latest_time