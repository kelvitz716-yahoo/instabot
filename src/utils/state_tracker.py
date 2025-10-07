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
        
    def is_valid_job(self, job_id: str) -> bool:
        """Check if a job ID represents a valid job with state"""
        if job_id == "jobs":  # Skip the jobs subdirectory
            return False
        job_path = os.path.join(JOB_BASE_DIR, "jobs", job_id)
        if not os.path.isdir(job_path):
            return False
        state_file = os.path.join(job_path, "job_state.json")
        return os.path.exists(state_file)

    def get_job_files(self, job_id: str) -> List[str]:
        """Get list of all files for a job"""
        if not self.is_valid_job(job_id):
            return []
            
        job_state = self.job_manager.get_job_state(job_id)
        if not job_state:
            return []
        
        files = list(job_state.files.keys())
        
        def get_file_number(filename: str) -> int:
            """Extract the number from filename pattern like ..._01.jpg"""
            try:
                # Split by underscore and get last part before extension
                num_part = filename.split('_')[-1].split('.')[0]
                return int(num_part)
            except (IndexError, ValueError):
                return 0
                
        return sorted(files, key=get_file_number)
            
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
            
    def list_jobs(self) -> List[str]:
        """List all valid jobs with job state files"""
        jobs_dir = os.path.join(JOB_BASE_DIR, "jobs")
        if not os.path.exists(jobs_dir):
            os.makedirs(jobs_dir)
            
        job_dirs = [d for d in os.listdir(jobs_dir) 
                   if os.path.isdir(os.path.join(jobs_dir, d))]
                   
        valid_jobs = [job for job in job_dirs if self.is_valid_job(job)]
        return sorted(valid_jobs)
            
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
            to_upload = sorted([
                str(fname) for fname, fstate in state.files.items()
                if fstate.status == FileStatus.DOWNLOADED
            ])
            
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
            
    def finalize_job(
        self, 
        job_id: str, 
        suppress_status: bool = False,
        duration: Optional[float] = None
    ) -> None:
        """
        Mark a job as completed and perform any necessary cleanup.
        Should be called after all files are processed.
        
        Args:
            job_id: The ID of the job to finalize
            suppress_status: If True, don't send an additional status message
            duration: Optional duration in seconds to record for the job
        """
        try:
            job_state = self.job_manager.get_job_state(job_id)
            if not job_state:
                logger.error(f"Cannot finalize job {job_id}: Job state not found")
                return
                
            if job_state.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
                # Check if any files failed
                failed_files = len([f for f in job_state.files.values() if f.status == FileStatus.FAILED])
                total_files = len(job_state.files)
                
                # Update job status based on failures
                new_status = JobStatus.COMPLETED
                if failed_files == total_files:
                    new_status = JobStatus.FAILED
                elif failed_files > 0:
                    new_status = JobStatus.PARTIALLY_COMPLETED
                    
                self.job_manager.update_job_state(
                    job_id, 
                    status=new_status,
                    duration=duration,
                    suppress_status=suppress_status
                )
        except Exception as e:
            logger.error(f"Error finalizing job {job_id}: {str(e)}")
            
    def get_job_summary(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a summary of the job's current state"""
        try:
            state = self.job_manager.get_job_state(job_id)
            if not state:
                # Don't raise an error, just return None for non-existent jobs
                logger.error(f"No state found for job {job_id}")
                return None
                
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