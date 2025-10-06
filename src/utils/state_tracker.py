"""
Manages the state of download and upload jobs with persistent tracking.
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from utils.job_manager import JobManager, JobState, JobStatus, FileState, FileStatus
from utils.file_naming import generate_filename
from utils.constants import JOB_BASE_DIR
from utils.service_manager import service_manager

logger = logging.getLogger(__name__)

class StateTracker:
    """
    Handles state management and coordination between download and upload processes.
    Ensures consistent state tracking and provides recovery mechanisms.
    """
    def __init__(self, job_manager: Optional[JobManager] = None):
        self.job_manager = job_manager or service_manager.get(JobManager)
        service_manager.register(StateTracker, self)
        
    def update_job_heartbeat(
        self,
        job_id: str,
        files_processed: int,
        total_files: int,
        current_operation: str,
        bytes_processed: int = 0
    ) -> None:
        """Update job heartbeat with current progress information"""
        self.job_manager.update_job_heartbeat(
            job_id,
            files_processed,
            total_files,
            current_operation,
            bytes_processed
        )
    
    def initialize_download_job(self, url: str, expected_count: int = 0) -> str:
        """
        Initialize a new download job for a given URL.
        Returns the job_id for tracking.
        """
        try:
            job_id = self.job_manager.create_job(url)
            self.job_manager.update_job_state(
                job_id,
                status=JobStatus.DOWNLOADING,
                expected_files=expected_count
            )
            logger.info(f"Initialized download job {job_id} for URL: {url}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to initialize download job for {url}: {str(e)}")
            raise
            
    def record_download(self, job_id: str, filename: str, original_url: str, file_size: int = 0) -> None:
        """Record a successful file download in the job state"""
        try:
            self.job_manager.add_file_to_job(job_id, filename, original_url)
            self.job_manager.update_file_state(
                job_id,
                filename,
                status=FileStatus.DOWNLOADED,
                file_size=file_size,
                download_time=datetime.now().timestamp()
            )
            logger.debug(f"Recorded download for {filename} in job {job_id}")
        except Exception as e:
            logger.error(f"Failed to record download state for {filename}: {str(e)}")
            raise
            
    def prepare_for_upload(self, job_id: str) -> List[str]:
        """
        Get list of files ready for upload, marking them as UPLOADING.
        Returns list of filenames to upload.
        """
        try:
            state = self.job_manager.get_job_state(job_id)
            if not state:
                raise ValueError(f"No state found for job {job_id}")
                
            # Find all downloaded files not yet uploaded
            to_upload = [
                fname for fname, fstate in state.files.items()
                if fstate.status == FileStatus.DOWNLOADED
            ]
            
            # Mark files as uploading
            for filename in to_upload:
                self.job_manager.update_file_state(
                    job_id,
                    filename,
                    status=FileStatus.UPLOADING
                )
                
            if to_upload:
                self.job_manager.update_job_state(job_id, status=JobStatus.UPLOADING)
                
            return to_upload
        except Exception as e:
            logger.error(f"Failed to prepare files for upload in job {job_id}: {str(e)}")
            raise
            
    def record_upload(self, job_id: str, filename: str, success: bool, error: Optional[str] = None) -> None:
        """Record the result of a file upload attempt"""
        try:
            status = FileStatus.UPLOADED if success else FileStatus.FAILED
            self.job_manager.update_file_state(
                job_id,
                filename,
                status=status,
                upload_time=datetime.now().timestamp(),
                error=error
            )
            logger.debug(f"Recorded upload {'success' if success else 'failure'} for {filename}")
        except Exception as e:
            logger.error(f"Failed to record upload state for {filename}: {str(e)}")
            raise
            
    def finalize_job(self, job_id: str) -> None:
        """
        Finalize a job, checking if all files are processed and updating state accordingly.
        """
        try:
            state = self.job_manager.get_job_state(job_id)
            if not state:
                raise ValueError(f"No state found for job {job_id}")
                
            # Check if all files are processed
            all_processed = all(
                fstate.status in (FileStatus.UPLOADED, FileStatus.FAILED)
                for fstate in state.files.values()
            )
            
            if all_processed:
                # Count successes and failures
                uploaded = sum(1 for f in state.files.values() if f.status == FileStatus.UPLOADED)
                failed = sum(1 for f in state.files.values() if f.status == FileStatus.FAILED)
                
                logger.info(f"Job {job_id} completed: {uploaded} uploaded, {failed} failed")
                
                self.job_manager.complete_job(job_id)
            else:
                logger.warning(f"Job {job_id} has unprocessed files")
                
        except Exception as e:
            logger.error(f"Failed to finalize job {job_id}: {str(e)}")
            raise
            
    def get_job_summary(self, job_id: str) -> Dict[str, Any]:
        """Get a summary of the job's current state"""
        try:
            state = self.job_manager.get_job_state(job_id)
            if not state:
                raise ValueError(f"No state found for job {job_id}")
                
            uploaded = sum(1 for f in state.files.values() if f.status == FileStatus.UPLOADED)
            failed = sum(1 for f in state.files.values() if f.status == FileStatus.FAILED)
            pending = sum(1 for f in state.files.values() if f.status in (FileStatus.PENDING, FileStatus.DOWNLOADING))
            uploading = sum(1 for f in state.files.values() if f.status == FileStatus.UPLOADING)
            
            duration = (
                state.end_time - state.start_time
                if state.end_time
                else datetime.now().timestamp() - state.start_time
            )
            
            return {
                "job_id": job_id,
                "status": state.status.value,
                "source_url": state.source_url,
                "stats": {
                    "total_files": len(state.files),
                    "uploaded": uploaded,
                    "failed": failed,
                    "pending": pending,
                    "uploading": uploading
                },
                "duration": duration,
                "error": state.error
            }
        except Exception as e:
            logger.error(f"Failed to get job summary for {job_id}: {str(e)}")
            raise