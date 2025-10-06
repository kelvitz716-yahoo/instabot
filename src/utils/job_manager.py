"""
Job management system for handling Instagram downloads and uploads.
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from .constants import JOB_BASE_DIR

logger = logging.getLogger(__name__)

from .service_manager import service_manager

class JSONSerializableEnum(Enum):
    """Base class for JSON serializable enums"""
    def to_json(self) -> str:
        return self.value
        
    @classmethod
    def from_json(cls, value: str) -> 'JSONSerializableEnum':
        return cls(value)

class JobStatus(JSONSerializableEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    RECOVERING = "recovering"  # Added for crash recovery

class FileStatus(JSONSerializableEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"

@dataclass
class FileState:
    filename: str
    status: FileStatus
    original_url: str
    download_time: Optional[float] = None
    upload_time: Optional[float] = None
    retries: int = 0
    error: Optional[str] = None
    file_size: int = 0  # Track file size for progress monitoring

@dataclass
class JobState:
    job_id: str
    source_url: str
    status: JobStatus
    start_time: float
    files: Dict[str, FileState]
    expected_files: int = 0
    end_time: Optional[float] = None
    error: Optional[str] = None
    last_heartbeat: Optional[float] = None  # Track last activity time

class EnumJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles our enum types"""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (JobStatus, FileStatus)):
            return obj.value
        if isinstance(obj, FileState):
            return asdict(obj)
        if isinstance(obj, JobState):
            return asdict(obj)
        return super().default(obj)

from utils.heartbeat import HeartbeatTracker

class JobManager:
    """Manages the lifecycle of download and upload jobs."""
    
    def __init__(self):
        """Initialize the job manager."""
        self._active_jobs = {}
        self.base_path = JOB_BASE_DIR
        self._heartbeat_tracker = HeartbeatTracker()
        self._recovery_system = None
        service_manager.register(JobManager, self)
        
    def initialize_recovery(self, recovery_system=None):
        """Initialize the recovery system after JobManager is registered."""
        if not self._recovery_system:
            from .recovery import RecoverySystem
            self._recovery_system = recovery_system or RecoverySystem(job_manager=self)

    def get_recovery_system(self):
        """Get the recovery system, initializing it if needed."""
        if not self._recovery_system:
            self.initialize_recovery()
        return self._recovery_system

    def _ensure_directories(self) -> None:
        """Create the base job directory if it doesn't exist"""
        os.makedirs(self.base_path, exist_ok=True)
        
    def get_stalled_jobs(self, timeout_seconds: int = 300) -> List[str]:
        """
        Get a list of job IDs that have been stalled (no heartbeat updates) for longer than the timeout
        
        Args:
            timeout_seconds: Number of seconds after which a job is considered stalled
            
        Returns:
            List of job IDs that are stalled
        """
        return self._heartbeat_tracker.get_stalled_jobs(timeout_seconds)
        
    def scan_for_recoverable_jobs(self) -> List[JobState]:
        """
        Scan for jobs that can be recovered after a crash or interruption.
        Returns a list of recoverable job states.
        """
        return self._recovery_system.scan_for_interrupted_jobs()

    def attempt_job_recovery(self, job_state: JobState) -> bool:
        """
        Attempt to recover an interrupted or failed job.
        
        Args:
            job_state: The state of the job to recover
            
        Returns:
            bool: True if recovery was successful, False otherwise
        """
        try:
            # Log recovery attempt
            logger.info(f"Attempting to recover job {job_state.job_id}")
            
            # Use recovery system to handle the recovery
            return self._recovery_system.resume_job(job_state)
            
        except Exception as e:
            logger.error(f"Failed to recover job {job_state.job_id}: {str(e)}")
            return False
        
    def create_job(self, source_url: str) -> str:
        """Create a new job and return its ID"""
        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        job_path = os.path.join(self.base_path, job_id)
        
        # Create job directory structure
        os.makedirs(job_path)
        os.makedirs(os.path.join(job_path, "media"))
        os.makedirs(os.path.join(job_path, "uploaded"))
        os.makedirs(os.path.join(job_path, "failed"))
        
        # Initialize job state
        job_state = JobState(
            job_id=job_id,
            source_url=source_url,
            status=JobStatus.PENDING,
            start_time=time.time(),
            files={}
        )
        
        # Save initial state
        self._save_job_state(job_path, job_state)
        
        # Create lock file
        with open(os.path.join(job_path, ".lock"), "w") as f:
            f.write(str(os.getpid()))
            
        return job_id
        
    def _save_job_state(self, job_path: str, state: JobState) -> None:
        """Save job state to job_state.json"""
        state_file = os.path.join(job_path, "job_state.json")
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2, cls=EnumJSONEncoder)
            
    def _load_job_state(self, job_path: str) -> Optional[JobState]:
        """Load job state from job_state.json"""
        state_file = os.path.join(job_path, "job_state.json")
        if not os.path.exists(state_file):
            return None
            
        with open(state_file, "r") as f:
            data = json.load(f)
            
        # Convert string values back to enums
        if "status" in data:
            data["status"] = JobStatus(data["status"])
        if "files" in data:
            for file_data in data["files"].values():
                if "status" in file_data:
                    file_data["status"] = FileStatus(file_data["status"])
            # Convert the loaded data back to JobState
            return JobState(
                job_id=data["job_id"],
                source_url=data["source_url"],
                status=JobStatus(data["status"]),
                start_time=data["start_time"],
                files={k: FileState(**v) for k, v in data["files"].items()},
                expected_files=data["expected_files"],
                end_time=data.get("end_time"),
                error=data.get("error")
            )
            
    def get_job_state(self, job_id: str) -> Optional[JobState]:
        """Get the current state of a job"""
        job_path = os.path.join(self.base_path, job_id)
        return self._load_job_state(job_path)
        
    def get_stalled_jobs(self, timeout_seconds: int = 300) -> List[str]:
        """
        Get a list of job IDs that have been stalled (no heartbeat updates) for longer than the timeout
        
        Args:
            timeout_seconds: Number of seconds after which a job is considered stalled
            
        Returns:
            List of job IDs that are stalled
        """
        return self._heartbeat_tracker.get_stalled_jobs(timeout_seconds)
        
    def update_job_heartbeat(
        self,
        job_id: str,
        files_processed: int,
        total_files: int,
        current_operation: str,
        bytes_processed: int = 0
    ) -> None:
        """Update the heartbeat information for a job"""
        self._heartbeat_tracker.update_heartbeat(
            job_id=job_id,
            files_processed=files_processed,
            total_files=total_files,
            current_operation=current_operation,
            bytes_processed=bytes_processed
        )
        
    def update_job_state(self, job_id: str, 
                        status: Optional[JobStatus] = None,
                        error: Optional[str] = None,
                        **kwargs) -> None:
        """Update job state with new information"""
        job_path = os.path.join(self.base_path, job_id)
        state = self._load_job_state(job_path)
        
        if not state:
            raise ValueError(f"No state found for job {job_id}")
            
        if status:
            state.status = status
        if error:
            state.error = error
            
        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
                
        self._save_job_state(job_path, state)
        
    def add_file_to_job(self, job_id: str, filename: str, 
                        original_url: str) -> None:
        """Add a new file to track in the job"""
        job_path = os.path.join(self.base_path, job_id)
        state = self._load_job_state(job_path)
        
        if not state:
            raise ValueError(f"No state found for job {job_id}")
            
        state.files[filename] = FileState(
            filename=filename,
            status=FileStatus.PENDING,
            original_url=original_url
        )
        
        self._save_job_state(job_path, state)
        
    def update_file_state(self, job_id: str, filename: str,
                         status: Optional[FileStatus] = None,
                         bytes_processed: int = 0,
                         **kwargs) -> None:
        """Update the state of a specific file in a job"""
        job_path = os.path.join(self.base_path, job_id)
        state = self._load_job_state(job_path)
        
        # Update heartbeat with progress
        self._heartbeat_tracker.update_heartbeat(
            job_id=job_id,
            files_processed=sum(1 for f in state.files.values() if f.status in [FileStatus.UPLOADED, FileStatus.FAILED]),
            total_files=len(state.files),
            current_operation=f"Processing {filename}",
            bytes_processed=bytes_processed
        )
        
        if not state or filename not in state.files:
            raise ValueError(f"File {filename} not found in job {job_id}")
            
        file_state = state.files[filename]
        if status:
            file_state.status = status
            
        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(file_state, key):
                setattr(file_state, key, value)
                
        self._save_job_state(job_path, state)
        
    def complete_job(self, job_id: str) -> None:
        """Mark a job as completed and clean up"""
        job_path = os.path.join(self.base_path, job_id)
        state = self._load_job_state(job_path)
        
        if not state:
            raise ValueError(f"No state found for job {job_id}")
            
        state.status = JobStatus.COMPLETED
        state.end_time = time.time()
        
        self._save_job_state(job_path, state)
        
        # Remove lock file
        lock_file = os.path.join(job_path, ".lock")
        if os.path.exists(lock_file):
            os.remove(lock_file)
            
    def is_job_locked(self, job_id: str) -> bool:
        """Check if a job is currently locked/in-progress"""
        lock_file = os.path.join(self.base_path, job_id, ".lock")
        return os.path.exists(lock_file)