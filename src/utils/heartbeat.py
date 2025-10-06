import time
from dataclasses import dataclass
from typing import Dict, Optional
from logger import get_logger

logger = get_logger(__name__)

@dataclass
class HeartbeatInfo:
    """Data class to store heartbeat information for a job"""
    job_id: str
    last_heartbeat: float
    files_processed: int
    total_files: int
    current_operation: str
    bytes_processed: int
    last_progress_update: float
    
    @property
    def progress_percentage(self) -> float:
        """Calculate the progress percentage"""
        if self.total_files == 0:
            return 0.0
        return (self.files_processed / self.total_files) * 100

    @property
    def is_making_progress(self) -> bool:
        """Check if the job has made progress since last heartbeat"""
        # Consider job stalled if no progress update in last 30 seconds
        return (time.time() - self.last_progress_update) < 30

class HeartbeatTracker:
    """Tracks job heartbeats and progress information"""
    
    def __init__(self, heartbeat_timeout: int = 60):
        self._heartbeats: Dict[str, HeartbeatInfo] = {}
        self.heartbeat_timeout = heartbeat_timeout
    
    def get_stalled_jobs(self, timeout_seconds: int = 300) -> list[str]:
        """
        Get a list of job IDs that have been stalled (no heartbeat updates) for longer than the timeout
        
        Args:
            timeout_seconds: Number of seconds after which a job is considered stalled
            
        Returns:
            List of job IDs that are stalled
        """
        stalled_jobs = []
        current_time = time.time()
        
        for job_id, heartbeat in self._heartbeats.items():
            time_since_update = current_time - heartbeat.last_heartbeat
            if time_since_update > timeout_seconds:
                stalled_jobs.append(job_id)
                
        return stalled_jobs

    def update_heartbeat(
        self,
        job_id: str,
        files_processed: int,
        total_files: int,
        current_operation: str,
        bytes_processed: int = 0
    ) -> None:
        """Update the heartbeat information for a job"""
        current_time = time.time()
        
        # Get existing heartbeat info or create new
        heartbeat = self._heartbeats.get(job_id)
        
        if heartbeat:
            # Check if there's actual progress
            if (files_processed > heartbeat.files_processed or
                bytes_processed > heartbeat.bytes_processed):
                progress_time = current_time
            else:
                progress_time = heartbeat.last_progress_update
        else:
            progress_time = current_time
            
        # Update heartbeat info
        self._heartbeats[job_id] = HeartbeatInfo(
            job_id=job_id,
            last_heartbeat=current_time,
            files_processed=files_processed,
            total_files=total_files,
            current_operation=current_operation,
            bytes_processed=bytes_processed,
            last_progress_update=progress_time
        )
        
        logger.debug(
            f"Updated heartbeat for job {job_id}: "
            f"{files_processed}/{total_files} files, "
            f"operation: {current_operation}"
        )
    
    def get_heartbeat(self, job_id: str) -> Optional[HeartbeatInfo]:
        """Get heartbeat information for a job"""
        return self._heartbeats.get(job_id)
    
    def remove_heartbeat(self, job_id: str) -> None:
        """Remove heartbeat tracking for a completed/failed job"""
        if job_id in self._heartbeats:
            del self._heartbeats[job_id]
            logger.debug(f"Removed heartbeat tracking for job {job_id}")
    
    def check_stalled_jobs(self) -> list[str]:
        """Check for jobs that have stopped making progress"""
        current_time = time.time()
        stalled_jobs = []
        
        for job_id, heartbeat in list(self._heartbeats.items()):
            # Check if heartbeat is too old
            if (current_time - heartbeat.last_heartbeat) > self.heartbeat_timeout:
                stalled_jobs.append(job_id)
                logger.warning(
                    f"Job {job_id} has not sent heartbeat in "
                    f"{self.heartbeat_timeout} seconds"
                )
            # Check if job is not making progress
            elif not heartbeat.is_making_progress:
                stalled_jobs.append(job_id)
                logger.warning(
                    f"Job {job_id} has not made progress in "
                    f"{int(current_time - heartbeat.last_progress_update)} seconds"
                )
                
        return stalled_jobs
    
    def get_job_status(self, job_id: str) -> dict:
        """Get detailed status information for a job"""
        heartbeat = self.get_heartbeat(job_id)
        if not heartbeat:
            return {"status": "unknown", "error": "No heartbeat information available"}
            
        current_time = time.time()
        heartbeat_age = current_time - heartbeat.last_heartbeat
        
        return {
            "status": "active" if heartbeat_age < self.heartbeat_timeout else "stalled",
            "progress": {
                "files_processed": heartbeat.files_processed,
                "total_files": heartbeat.total_files,
                "percentage": heartbeat.progress_percentage,
                "current_operation": heartbeat.current_operation,
                "bytes_processed": heartbeat.bytes_processed,
                "last_update": heartbeat_age,
                "making_progress": heartbeat.is_making_progress
            }
        }