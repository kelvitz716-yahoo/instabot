"""
Reporting system for tracking and analyzing download/upload jobs.
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from utils.state_tracker import StateTracker
from utils.constants import JOB_BASE_DIR
from utils.job_manager import JobStatus, FileStatus
from utils.service_manager import service_manager

logger = logging.getLogger(__name__)

class ReportingSystem:
    """
    Handles job reporting, statistics tracking, and performance analytics.
    """
    def __init__(self, state_tracker: Optional[StateTracker] = None):
        self.state_tracker = state_tracker or service_manager.get(StateTracker)
        service_manager.register(ReportingSystem, self)
        
    async def report_job_stuck(self, job_id: str, duration: int) -> None:
        """Report a job as stuck"""
        message = f"⚠️ Job {job_id} appears to be stuck (no progress for {duration} seconds)"
        logger.warning(message)
        # Add any notification mechanisms here (e.g., Telegram messages)
        
    def get_active_jobs_report(self) -> Dict[str, Any]:
        """Get a summary of all currently active jobs"""
        active_jobs = []
        total_files = 0
        total_size = 0
        
        for job_id in self._get_active_job_ids():
            try:
                summary = self.state_tracker.get_job_summary(job_id)
                if summary:
                    active_jobs.append(summary)
                    total_files += summary['stats']['total_files']
                    total_size += self._get_job_size(job_id)
            except Exception as e:
                logger.error(f"Error getting summary for job {job_id}: {str(e)}")
                
        return {
            "active_jobs_count": len(active_jobs),
            "total_files_in_progress": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "jobs": active_jobs
        }
        
    def get_job_performance_metrics(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed performance metrics for a specific job"""
        try:
            summary = self.state_tracker.get_job_summary(job_id)
            if not summary:
                return None
                
            files = self._get_job_files(job_id)
            total_size = sum(os.path.getsize(f) for f in files)
            
            # Calculate durations
            download_duration = self._calculate_download_duration(job_id)
            upload_duration = self._calculate_upload_duration(job_id)
            
            return {
                "job_id": job_id,
                "status": summary['status'],
                "metrics": {
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "download_speed_mbps": round(total_size / (download_duration * 1024 * 1024), 2) if download_duration else 0,
                    "upload_speed_mbps": round(total_size / (upload_duration * 1024 * 1024), 2) if upload_duration else 0,
                    "download_duration_sec": round(download_duration, 2),
                    "upload_duration_sec": round(upload_duration, 2),
                    "total_duration_sec": round(summary.get('duration', 0), 2)
                },
                "stats": summary['stats'],
                "error": summary.get('error')
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics for job {job_id}: {str(e)}")
            return None
            
    def get_system_health_report(self) -> Dict[str, Any]:
        """Get overall system health metrics"""
        try:
            active_jobs = self._get_active_job_ids()
            stuck_jobs = self._find_stuck_jobs()
            failed_jobs = self._get_failed_jobs()
            
            # Calculate success rate
            completed_jobs = self._get_completed_jobs()
            total_jobs = len(completed_jobs) + len(failed_jobs)
            success_rate = (len(completed_jobs) / total_jobs * 100) if total_jobs > 0 else 100
            
            return {
                "status": "healthy" if not stuck_jobs else "warning",
                "active_jobs": len(active_jobs),
                "stuck_jobs": len(stuck_jobs),
                "failed_jobs": len(failed_jobs),
                "success_rate_percent": round(success_rate, 2),
                "storage": self._get_storage_metrics(),
                "issues": [
                    {"job_id": job_id, "reason": "stuck", "duration": self._get_job_stuck_duration(job_id)}
                    for job_id in stuck_jobs
                ]
            }
        except Exception as e:
            logger.error(f"Error generating system health report: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    def get_periodic_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get statistics for jobs over the specified time period"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            jobs = self._get_jobs_since(cutoff_time)
            
            total_size = 0
            successful_jobs = 0
            failed_jobs = 0
            total_files = 0
            successful_files = 0
            failed_files = 0
            
            for job_id in jobs:
                try:
                    metrics = self.get_job_performance_metrics(job_id)
                    if not metrics:
                        continue
                        
                    total_size += metrics['metrics']['total_size_mb']
                    if metrics['status'] == JobStatus.COMPLETED.value:
                        successful_jobs += 1
                        successful_files += metrics['stats']['uploaded']
                    elif metrics['status'] == JobStatus.FAILED.value:
                        failed_jobs += 1
                        failed_files += metrics['stats']['failed']
                        
                    total_files += metrics['stats']['total_files']
                except Exception as e:
                    logger.error(f"Error processing job {job_id} for periodic report: {str(e)}")
                    
            return {
                "period_hours": hours,
                "total_jobs": len(jobs),
                "successful_jobs": successful_jobs,
                "failed_jobs": failed_jobs,
                "total_files": total_files,
                "successful_files": successful_files,
                "failed_files": failed_files,
                "total_size_mb": round(total_size, 2),
                "success_rate_percent": round(successful_jobs / len(jobs) * 100, 2) if jobs else 100
            }
        except Exception as e:
            logger.error(f"Error generating periodic report: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
            
    def _get_active_job_ids(self) -> List[str]:
        """Get list of currently active job IDs"""
        active_statuses = {JobStatus.DOWNLOADING.value, JobStatus.UPLOADING.value}
        return [
            job_id for job_id in os.listdir(JOB_BASE_DIR)
            if os.path.isdir(os.path.join(JOB_BASE_DIR, job_id))
            and self._get_job_status(job_id) in active_statuses
        ]
        
    def _get_job_size(self, job_id: str) -> int:
        """Calculate total size of all files in a job"""
        job_dir = os.path.join(JOB_BASE_DIR, job_id)
        total_size = 0
        
        for root, _, files in os.walk(job_dir):
            for file in files:
                if not file.endswith(('.json', '.txt')):
                    try:
                        total_size += os.path.getsize(os.path.join(root, file))
                    except OSError:
                        continue
                        
        return total_size
        
    def _get_job_files(self, job_id: str) -> List[str]:
        """Get list of all media files in a job"""
        job_dir = os.path.join(JOB_BASE_DIR, job_id)
        files = []
        
        for root, _, filenames in os.walk(job_dir):
            for filename in filenames:
                if not filename.endswith(('.json', '.txt')):
                    files.append(os.path.join(root, filename))
                    
        return files
        
    def _calculate_download_duration(self, job_id: str) -> float:
        """Calculate total download duration for a job"""
        summary = self.state_tracker.get_job_summary(job_id)
        if not summary:
            return 0
            
        start_time = summary.get('start_time', 0)
        first_upload = float('inf')
        
        state = self.state_tracker.job_manager.get_job_state(job_id)
        if not state:
            return 0
            
        for file_state in state.files.values():
            if file_state.upload_time:
                first_upload = min(first_upload, file_state.upload_time)
                
        return first_upload - start_time if first_upload != float('inf') else 0
        
    def _calculate_upload_duration(self, job_id: str) -> float:
        """Calculate total upload duration for a job"""
        state = self.state_tracker.job_manager.get_job_state(job_id)
        if not state:
            return 0
            
        upload_times = []
        for file_state in state.files.values():
            if file_state.upload_time:
                upload_times.append(file_state.upload_time)
                
        if not upload_times:
            return 0
            
        return max(upload_times) - min(upload_times)
        
    def _find_stuck_jobs(self, timeout_minutes: int = 30) -> List[str]:
        """Find jobs that appear to be stuck"""
        stuck_jobs = []
        cutoff_time = datetime.now().timestamp() - (timeout_minutes * 60)
        
        for job_id in self._get_active_job_ids():
            state = self.state_tracker.job_manager.get_job_state(job_id)
            if not state:
                continue
                
            # Check if job is old and still active
            if state.start_time < cutoff_time and state.status in (JobStatus.DOWNLOADING, JobStatus.UPLOADING):
                stuck_jobs.append(job_id)
                
        return stuck_jobs
        
    def _get_storage_metrics(self) -> Dict[str, float]:
        """Get storage usage metrics"""
        total_size = 0
        for job_id in os.listdir(JOB_BASE_DIR):
            job_path = os.path.join(JOB_BASE_DIR, job_id)
            if os.path.isdir(job_path):
                total_size += sum(
                    os.path.getsize(os.path.join(root, file))
                    for root, _, files in os.walk(job_path)
                    for file in files
                )
                
        return {
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "jobs_count": len(os.listdir(JOB_BASE_DIR))
        }
        
    def _get_completed_jobs(self) -> List[str]:
        """Get list of successfully completed jobs"""
        return [
            job_id for job_id in os.listdir(JOB_BASE_DIR)
            if os.path.isdir(os.path.join(JOB_BASE_DIR, job_id))
            and self._get_job_status(job_id) == JobStatus.COMPLETED.value
        ]
        
    def _get_failed_jobs(self) -> List[str]:
        """Get list of failed jobs"""
        return [
            job_id for job_id in os.listdir(JOB_BASE_DIR)
            if os.path.isdir(os.path.join(JOB_BASE_DIR, job_id))
            and self._get_job_status(job_id) == JobStatus.FAILED.value
        ]
        
    def _get_job_status(self, job_id: str) -> Optional[str]:
        """Get current status of a job"""
        try:
            summary = self.state_tracker.get_job_summary(job_id)
            return summary['status'] if summary else None
        except Exception:
            return None
            
    def _get_jobs_since(self, timestamp: datetime) -> List[str]:
        """Get list of jobs created after the given timestamp"""
        cutoff = timestamp.timestamp()
        jobs = []
        
        for job_id in os.listdir(JOB_BASE_DIR):
            job_path = os.path.join(JOB_BASE_DIR, job_id)
            if os.path.isdir(job_path):
                try:
                    state = self.state_tracker.job_manager.get_job_state(job_id)
                    if state and state.start_time >= cutoff:
                        jobs.append(job_id)
                except Exception:
                    continue
                    
        return jobs
        
    def _get_job_stuck_duration(self, job_id: str) -> float:
        """Get duration in minutes that a job has been stuck"""
        state = self.state_tracker.job_manager.get_job_state(job_id)
        if not state:
            return 0
            
        last_activity = state.start_time
        for file_state in state.files.values():
            if file_state.upload_time:
                last_activity = max(last_activity, file_state.upload_time)
                
        return (datetime.now().timestamp() - last_activity) / 60  # Convert to minutes