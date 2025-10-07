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

class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (JobStatus, FileStatus)):
            return obj.value
        return super().default(obj)

@dataclass
class FileState:
    filename: str
    status: FileStatus
    original_url: str
    download_time: Optional[float] = None
    upload_time: Optional[float] = None
    error: Optional[str] = None
    retries: int = 0
    file_size: int = 0  # Track file size for progress monitoring

@dataclass
class JobState:
    """Represents the state of a download/upload job"""
    job_id: str
    source_url: str
    status: JobStatus
    start_time: float
    files: Dict[str, FileState]
    end_time: Optional[float] = None
    error: Optional[str] = None
    download_opts: Optional[Dict[str, Any]] = None
    expected_files: Optional[int] = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary"""
        data = asdict(self)
        # Convert enums to their string values
        data['status'] = self.status.value
        for filename, file_state in data['files'].items():
            if isinstance(file_state['status'], FileStatus):
                data['files'][filename]['status'] = file_state['status'].value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobState':
        """Create JobState from a dictionary"""
        # Convert string values back to enums
        data['status'] = JobStatus(data['status'])
        files = {}
        for filename, file_state in data['files'].items():
            files[filename] = FileState(
                filename=filename,
                status=FileStatus(file_state['status']),
                original_url=file_state['original_url'],
                download_time=file_state.get('download_time'),
                upload_time=file_state.get('upload_time'),
                error=file_state.get('error'),
                retries=file_state.get('retries', 0),
                file_size=file_state.get('file_size', 0)
            )
        data['files'] = files
        return cls(**data)

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
        
        # Ensure base directories exist
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(os.path.join(self.base_path, "jobs"), exist_ok=True)
        
        service_manager.register(JobManager, self)
        
    def initialize_recovery(self, recovery_system=None):
        """Initialize the recovery system after JobManager is registered."""
        if not self._recovery_system:
            from .recovery import RecoverySystem
            self._recovery_system = recovery_system or RecoverySystem(job_manager=self)
            
        # Clean up old job directories without valid state
        self._cleanup_invalid_jobs()

    def get_recovery_system(self):
        """Get the recovery system, initializing it if needed."""
        if not self._recovery_system:
            self.initialize_recovery()
        return self._recovery_system

    def _ensure_directories(self) -> None:
        """Create the base job directory if it doesn't exist"""
        os.makedirs(self.base_path, exist_ok=True)
        
    def _cleanup_invalid_jobs(self) -> None:
        """Clean up job directories without valid state files"""
        jobs_dir = os.path.join(self.base_path, "jobs")
        if not os.path.exists(jobs_dir):
            return
            
        for job_id in os.listdir(jobs_dir):
            job_path = os.path.join(jobs_dir, job_id)
            if not os.path.isdir(job_path):
                continue
                
            state_file = os.path.join(job_path, "job_state.json")
            if not os.path.exists(state_file):
                logger.warning(f"Found job directory without state file: {job_id}")
                continue
                
            try:
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                JobState.from_dict(state_data)  # Validate state structure
            except Exception as e:
                logger.error(f"Invalid state file for job {job_id}: {str(e)}")
                continue
            
            required_dirs = ["media", "uploaded", "failed"]
            missing_dirs = [d for d in required_dirs 
                          if not os.path.isdir(os.path.join(job_path, d))]
            
            if missing_dirs:
                # Create missing directories instead of failing the job
                for dirname in missing_dirs:
                    os.makedirs(os.path.join(job_path, dirname), exist_ok=True)
                logger.info(f"Created missing directories for job {job_id}: {missing_dirs}")
        
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
        job_path = os.path.join(self.base_path, "jobs", job_id)
        
        # Create job directory structure
        if not os.path.exists(job_path):
            os.makedirs(job_path, exist_ok=True)
            os.makedirs(os.path.join(job_path, "media"), exist_ok=True)
            os.makedirs(os.path.join(job_path, "uploaded"), exist_ok=True) 
            os.makedirs(os.path.join(job_path, "failed"), exist_ok=True)
        
        # Initialize job state
        job_state = JobState(
            job_id=job_id,
            source_url=source_url,
            status=JobStatus.PENDING,
            start_time=time.time(),
            files={},
            expected_files=0
        )
        
        # Add to active jobs
        self._active_jobs[job_id] = job_state
        
        # Save initial state
        self._save_job_state(job_path, job_state)
        
        # Create lock file
        with open(os.path.join(job_path, ".lock"), "w") as f:
            f.write(str(os.getpid()))
            
        return job_id
        
    def _save_job_state(self, job_path: str, state: JobState) -> None:
        """Save the job state to disk with backup on failure"""
        state_file = os.path.join(job_path, "job_state.json")
        temp_file = os.path.join(job_path, "job_state.json.tmp")
        backup_file = os.path.join(job_path, "job_state.json.bak")
        
        try:
            # First validate the state object can be serialized
            state_dict = state.to_dict()
            try:
                # Test that we can round-trip through JSON
                test_state = JobState.from_dict(json.loads(json.dumps(state_dict)))
            except Exception as e:
                logger.error(f"Invalid job state data: {str(e)}")
                raise
            
            # Write to temp file only after validation
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            with open(temp_file, "w") as f:
                json.dump(state_dict, f, indent=4)
                
            # If temp write successful, backup existing state if present
            if os.path.exists(state_file):
                try:
                    os.replace(state_file, backup_file)
                except Exception as e:
                    logger.warning(f"Failed to create backup state file: {str(e)}")
                    
            # Move temp to actual state file
            os.replace(temp_file, state_file)
            
        except Exception as e:
            logger.error(f"Failed to save state file {state_file}: {str(e)}")
            if os.path.exists(backup_file):
                try:
                    # Restore from backup if save failed
                    os.replace(backup_file, state_file)
                    logger.info("Restored state file from backup")
                    return
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {str(restore_error)}")
            raise
            
    def _load_job_state(self, job_path: str) -> Optional[JobState]:
        """Load job state from job_state.json"""
        job_id = os.path.basename(job_path)
        
        # If state is already in memory, return it
        if job_id in self._active_jobs:
            return self._active_jobs[job_id]
        
        state_file = os.path.join(job_path, "job_state.json")
        if not os.path.exists(state_file):
            return None
            
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
            state = JobState.from_dict(data)
            self._active_jobs[job_id] = state  # Cache in memory
            return state
        except Exception as e:
            logger.error(f"Failed to load state file {state_file}: {str(e)}")
            return None
            
    def validate_job_directory(self, job_id: str, repair: bool = True) -> bool:
        """
        Validate that a job directory has the expected structure.
        If repair=True, try to fix common issues like missing directories.
        """
        if job_id == "jobs":
            return False
            
        job_path = os.path.join(self.base_path, "jobs", job_id)
        if not os.path.isdir(job_path):
            return False
        
        # Check for job state file
        state_file = os.path.join(job_path, "job_state.json")
        if not os.path.exists(state_file):
            logger.error(f"No state file found for job {job_id}")
            return False
            
        # Validate state file contents
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            JobState.from_dict(state_data)
        except Exception as e:
            logger.error(f"Invalid state file for job {job_id}: {str(e)}")
            return False
            
        # Check for required directories
        required_dirs = ["media", "uploaded", "failed"]
        missing_dirs = [d for d in required_dirs 
                       if not os.path.isdir(os.path.join(job_path, d))]
                       
        if missing_dirs:
            if repair:
                # Create missing directories
                for dirname in missing_dirs:
                    os.makedirs(os.path.join(job_path, dirname), exist_ok=True)
                logger.info(f"Created missing directories for job {job_id}: {missing_dirs}")
            else:
                logger.error(f"Missing required directories for job {job_id}: {missing_dirs}")
                return False
                
        return True
            
    def get_job_state(self, job_id: str) -> Optional[JobState]:
        """Get the state of a specific job"""
        if not self.validate_job_directory(job_id):
            return None
            
        state_file = os.path.join(self.base_path, "jobs", job_id, "job_state.json")
        try:
            with open(state_file, 'r') as f:
                state_data = json.load(f)
            return JobState.from_dict(state_data)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.error(f"Error reading job state for {job_id}: {str(e)}")
            return None
            
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
                        suppress_status: bool = False,
                        **kwargs) -> None:
        """
        Update job state with new information.
        
        Args:
            job_id: The ID of the job to update
            status: Optional new status for the job
            error: Optional error message
            suppress_status: If True, don't send a status message update
            **kwargs: Additional state fields to update
        """
        job_path = os.path.join(self.base_path, "jobs", job_id)
        state = self._load_job_state(job_path)
        
        if not state:
            raise ValueError(f"No state found for job {job_id}")
            
        if status:
            state.status = status
        if error:
            state.error = error
        if 'duration' in kwargs:
            state.duration = kwargs['duration']
            
        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
                
        self._active_jobs[job_id] = state
        self._save_job_state(job_path, state)
        
    def add_file_to_job(self, job_id: str, filename: str, 
                        original_url: str) -> None:
        """Add a new file to track in the job"""
        job_path = os.path.join(self.base_path, "jobs", job_id)
        state = self._load_job_state(job_path)
        
        if not state:
            raise ValueError(f"No state found for job {job_id}")
            
        state.files[filename] = FileState(
            filename=filename,
            status=FileStatus.PENDING,
            original_url=original_url
        )
        
        self._active_jobs[job_id] = state
        self._save_job_state(job_path, state)
        
    def update_file_state(self, job_id: str, filename: str,
                         status: Optional[FileStatus] = None,
                         bytes_processed: int = 0,
                         **kwargs) -> None:
        """Update the state of a specific file in a job"""
        job_path = os.path.join(self.base_path, "jobs", job_id)
        state = self._load_job_state(job_path)
        
        if not state or filename not in state.files:
            raise ValueError(f"File {filename} not found in job {job_id}")
            
        # Update heartbeat with progress
        self._heartbeat_tracker.update_heartbeat(
            job_id=job_id,
            files_processed=sum(1 for f in state.files.values() if f.status in [FileStatus.UPLOADED, FileStatus.FAILED]),
            total_files=len(state.files),
            current_operation=f"Processing {filename}",
            bytes_processed=bytes_processed
        )
            
        file_state = state.files[filename]
        if status:
            file_state.status = status
            
        # Update any additional fields
        for key, value in kwargs.items():
            if hasattr(file_state, key):
                setattr(file_state, key, value)
                
        self._active_jobs[job_id] = state
        self._save_job_state(job_path, state)
        
    def complete_job(self, job_id: str) -> None:
        """Mark a job as completed and clean up"""
        job_path = os.path.join(self.base_path, "jobs", job_id)
        state = self._load_job_state(job_path)
        
        if not state:
            raise ValueError(f"No state found for job {job_id}")
            
        state.status = JobStatus.COMPLETED
        state.end_time = time.time()
        
        self._save_job_state(job_path, state)
        
        # Update active jobs
        self._active_jobs[job_id] = state
        
        # Remove lock file
        lock_file = os.path.join(job_path, ".lock")
        if os.path.exists(lock_file):
            os.remove(lock_file)
        
        # Remove from active jobs if completed
        if state.status == JobStatus.COMPLETED:
            self._active_jobs.pop(job_id, None)
            
    def is_job_locked(self, job_id: str) -> bool:
        """Check if a job is currently locked/in-progress"""
        lock_file = os.path.join(self.base_path, "jobs", job_id, ".lock")
        return os.path.exists(lock_file)