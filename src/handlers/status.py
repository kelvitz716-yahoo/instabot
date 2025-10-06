"""
Status command handler for bot statistics and health information.
"""
from telegram import Update
from telegram.ext import ContextTypes
from utils.ui_helper import format_mission_status
from utils.service_manager import service_manager
from utils.reporting import ReportingSystem
from utils.job_manager import JobManager

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - show comprehensive system status"""
    reporting = service_manager.get(ReportingSystem)
    job_manager = service_manager.get(JobManager)
    
    # Get system health metrics
    health_report = reporting.get_system_health_report()
    
    # Get download stats
    stats = reporting.get_periodic_report(hours=24)  # Last 24 hours
    
    # Format and send status message
    status_msg = format_mission_status(health_report, stats)
    await update.message.reply_text(status_msg)