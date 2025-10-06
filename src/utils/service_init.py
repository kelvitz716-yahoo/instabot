"""
Service initialization module to handle proper startup order.
"""
from typing import Optional
import logging

from .job_manager import JobManager
from .state_tracker import StateTracker
from .reporting import ReportingSystem
from .recovery import RecoverySystem

logger = logging.getLogger(__name__)

def initialize_services():
    """
    Initialize all services in the correct order to prevent circular dependencies.
    """
    try:
        # Create services
        job_manager = JobManager()
        state_tracker = StateTracker(job_manager=job_manager)
        reporting_system = ReportingSystem(state_tracker=state_tracker)
        recovery_system = RecoverySystem(job_manager=job_manager)
        
        # Link up reporting system
        recovery_system.set_reporting_system(reporting_system)
        
        # Initialize recovery last
        job_manager.initialize_recovery(recovery_system)
        
        logger.info("All services initialized successfully")
        return {
            'job_manager': job_manager,
            'state_tracker': state_tracker,
            'reporting_system': reporting_system,
            'recovery_system': recovery_system
        }
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise