"""
Job monitoring system for detecting and handling stuck jobs.
"""
import time
import asyncio
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from .job_manager import JobManager, JobState, JobStatus
from .service_manager import service_manager
from .reporting import ReportingSystem

logger = logging.getLogger(__name__)

class JobMonitor:
    """
    Monitors jobs for inactivity and handles stuck jobs.
    """
    def __init__(
        self,
        job_manager: Optional[JobManager] = None,
        reporting_system: Optional[ReportingSystem] = None,
        job_timeout: int = 3600,  # 1 hour default timeout
        progress_threshold: int = 300  # 5 minutes without progress is considered stuck
    ):
        self.job_manager = job_manager or service_manager.get(JobManager)
        self.reporting_system = reporting_system or service_manager.get(ReportingSystem)
        self.job_timeout = job_timeout
        self.progress_threshold = progress_threshold
        self.active_jobs: Dict[str, float] = {}  # job_id -> last_progress_time
        self.monitored_jobs: Set[str] = set()
        self._monitor_task: Optional[asyncio.Task] = None
        service_manager.register(JobMonitor, self)

    async def start_monitoring(self) -> None:
        """Start the job monitoring loop."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("Job monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the job monitoring loop."""
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
            logger.info("Job monitoring stopped")

    def register_job(self, job_id: str) -> None:
        """Register a job for monitoring."""
        self.active_jobs[job_id] = time.time()
        self.monitored_jobs.add(job_id)
        logger.debug(f"Registered job {job_id} for monitoring")

    def unregister_job(self, job_id: str) -> None:
        """Unregister a job from monitoring."""
        self.active_jobs.pop(job_id, None)
        self.monitored_jobs.discard(job_id)
        logger.debug(f"Unregistered job {job_id} from monitoring")

    def update_job_progress(self, job_id: str) -> None:
        """Update the last progress time for a job."""
        if job_id in self.monitored_jobs:
            self.active_jobs[job_id] = time.time()
            logger.debug(f"Updated progress for job {job_id}")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop that checks for stuck jobs."""
        while True:
            try:
                current_time = time.time()
                stuck_jobs = []

                # Check all monitored jobs
                for job_id in list(self.monitored_jobs):
                    last_progress = self.active_jobs.get(job_id)
                    if last_progress is None:
                        continue

                    time_since_progress = current_time - last_progress
                    job_state = self.job_manager.get_job_state(job_id)

                    if job_state and time_since_progress > self.progress_threshold:
                        if job_state.status in [JobStatus.DOWNLOADING, JobStatus.UPLOADING]:
                            stuck_jobs.append((job_id, job_state))

                # Handle stuck jobs
                for job_id, job_state in stuck_jobs:
                    await self._handle_stuck_job(job_id, job_state)

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in job monitor loop: {str(e)}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _handle_stuck_job(self, job_id: str, job_state: JobState) -> None:
        """Handle a stuck job by marking it as failed and notifying."""
        try:
            # Mark the job as failed
            job_state.status = JobStatus.FAILED
            job_state.error = f"Job stuck - no progress for {self.progress_threshold} seconds"
            
            # Save the updated state
            self.job_manager._save_job_state(
                f"{self.job_manager.base_path}/{job_id}",
                job_state
            )

            # Notify through reporting system
            await self.reporting_system.report_job_stuck(
                job_id,
                duration=self.progress_threshold
            )

            # Unregister the job from monitoring
            self.unregister_job(job_id)
            
            logger.warning(f"Job {job_id} marked as stuck and failed")

        except Exception as e:
            logger.error(f"Error handling stuck job {job_id}: {str(e)}")

    def get_stuck_jobs(self) -> List[JobState]:
        """Get a list of currently stuck jobs."""
        stuck_jobs = []
        current_time = time.time()

        for job_id in self.monitored_jobs:
            last_progress = self.active_jobs.get(job_id)
            if last_progress and (current_time - last_progress) > self.progress_threshold:
                job_state = self.job_manager.get_job_state(job_id)
                if job_state:
                    stuck_jobs.append(job_state)

        return stuck_jobs