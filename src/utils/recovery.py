"""
Recovery system for handling interrupted jobs and crash recovery.
"""
import os
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from .job_manager import JobManager, JobState, JobStatus, FileStatus
from .service_manager import service_manager

logger = logging.getLogger(__name__)

class RecoverySystem:
    """
    Handles crash recovery and job resumption functionality.
    """
    def __init__(self, job_manager: Optional[JobManager] = None):
        self.job_manager = job_manager or service_manager.get(JobManager)
        self.max_job_age = timedelta(days=7)  # Don't try to recover jobs older than this
        self.inactive_timeout = timedelta(hours=1)  # Consider a job stuck if no updates for this long
        service_manager.register(RecoverySystem, self)

    def scan_for_interrupted_jobs(self) -> List[JobState]:
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
                    logger.info(f"Found interrupted job: {job_id}")
                    interrupted_jobs.append(job_state)

        return interrupted_jobs

    def resume_job(self, job_state: JobState) -> bool:
        """
        Attempt to resume an interrupted job.
        Returns True if the job can be resumed, False otherwise.
        """
        try:
            # Mark incomplete files as failed
            files_to_retry = []
            for file_state in job_state.files.values():
                if file_state.status in [FileStatus.DOWNLOADING, FileStatus.UPLOADING]:
                    if file_state.retries < 3:  # Allow up to 3 retries
                        files_to_retry.append(file_state)
                    else:
                        file_state.status = FileStatus.FAILED
                        file_state.error = "Max retries exceeded during recovery"

            if not files_to_retry:
                logger.info(f"No files eligible for retry in job {job_state.job_id}")
                job_state.status = JobStatus.FAILED
                self.job_manager._save_job_state(
                    os.path.join(self.job_manager.base_path, job_state.job_id),
                    job_state
                )
                return False

            # Update job state for retry
            job_state.status = JobStatus.PENDING
            self.job_manager._save_job_state(
                os.path.join(self.job_manager.base_path, job_state.job_id),
                job_state
            )
            return True

        except Exception as e:
            logger.error(f"Error resuming job {job_state.job_id}: {str(e)}")
            return False

    def _get_active_job_ids(self) -> List[str]:
        """Get list of job IDs in the jobs directory."""
        try:
            return [d for d in os.listdir(self.job_manager.base_path)
                   if os.path.isdir(os.path.join(self.job_manager.base_path, d))]
        except Exception as e:
            logger.error(f"Error scanning jobs directory: {str(e)}")
            return []

    def _get_last_update_time(self, job_state: JobState) -> datetime:
        """
        Get the timestamp of the last file status update in a job.
        Falls back to job start time if no updates found.
        """
        latest = job_state.start_time

        for file_state in job_state.files.values():
            if file_state.download_time and file_state.download_time > latest:
                latest = file_state.download_time
            if file_state.upload_time and file_state.upload_time > latest:
                latest = file_state.upload_time

        return datetime.fromtimestamp(latest)