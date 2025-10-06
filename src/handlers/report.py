"""
Handlers for reporting-related commands
"""
import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils.reporting import ReportingSystem
from utils.service_manager import service_manager
from utils.state_tracker import StateTracker
from utils.telegram_helper import split_large_message

logger = logging.getLogger(__name__)

class ReportHandler:
    """Handles reporting-related commands"""
    
    def __init__(self, state_tracker: Optional[StateTracker] = None, reporting_system: Optional[ReportingSystem] = None):
        self.state_tracker = state_tracker or service_manager.get(StateTracker)
        self.reporting_system = reporting_system or service_manager.get(ReportingSystem)
        service_manager.register(ReportHandler, self)
        
    async def handle_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command - show current statistics"""
        try:
            # Get active jobs report
            active = self.reporting.get_active_jobs_report()
            
            # Get 24-hour statistics
            daily = self.reporting.get_periodic_report(hours=24)
            
            # Format message
            message = (
                "📊 Current Statistics:\n\n"
                f"Active Jobs: {active['active_jobs_count']}\n"
                f"Files in Progress: {active['total_files_in_progress']}\n"
                f"Current Queue Size: {active['total_size_mb']}MB\n\n"
                "📈 24-Hour Summary:\n"
                f"Total Jobs: {daily['total_jobs']}\n"
                f"Success Rate: {daily['success_rate_percent']}%\n"
                f"Files Processed: {daily['successful_files']}/{daily['total_files']}\n"
                f"Total Data: {daily['total_size_mb']}MB"
            )
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error handling stats command: {str(e)}")
            await update.message.reply_text("❌ Error generating statistics")
            
    async def handle_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /health command - show system health status"""
        try:
            health = self.reporting.get_system_health_report()
            
            status_emoji = "✅" if health['status'] == "healthy" else "⚠️"
            
            message = (
                f"{status_emoji} System Status: {health['status'].upper()}\n\n"
                f"Active Jobs: {health['active_jobs']}\n"
                f"Success Rate: {health['success_rate_percent']}%\n"
                f"Storage Used: {health['storage']['total_size_mb']}MB\n"
                f"Total Jobs: {health['storage']['jobs_count']}\n"
            )
            
            if health['stuck_jobs']:
                message += "\n⚠️ Stuck Jobs:\n"
                for issue in health['issues']:
                    message += f"• Job {issue['job_id']}: Stuck for {issue['duration']:.1f} minutes\n"
                    
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error handling health command: {str(e)}")
            await update.message.reply_text("❌ Error checking system health")
            
    async def handle_job_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /job command - show detailed job information"""
        try:
            if not context.args:
                await update.message.reply_text("Please provide a job ID")
                return
                
            job_id = context.args[0]
            metrics = self.reporting.get_job_performance_metrics(job_id)
            
            if not metrics:
                await update.message.reply_text(f"❌ No information found for job {job_id}")
                return
                
            message = (
                f"📋 Job {job_id}\n"
                f"Status: {metrics['status']}\n\n"
                "📊 Statistics:\n"
                f"Total Files: {metrics['stats']['total_files']}\n"
                f"Uploaded: {metrics['stats']['uploaded']}\n"
                f"Failed: {metrics['stats']['failed']}\n"
                f"Size: {metrics['metrics']['total_size_mb']}MB\n\n"
                "⚡ Performance:\n"
                f"Download Speed: {metrics['metrics']['download_speed_mbps']}MB/s\n"
                f"Upload Speed: {metrics['metrics']['upload_speed_mbps']}MB/s\n"
                f"Total Duration: {metrics['metrics']['total_duration_sec']}s"
            )
            
            if metrics['error']:
                message += f"\n\n❌ Error: {metrics['error']}"
                
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error handling job info command: {str(e)}")
            await update.message.reply_text("❌ Error retrieving job information")

def get_report_handlers():
    """Get all reporting-related command handlers"""
    handler = ReportHandler()
    return [
        CommandHandler("stats", handler.handle_stats),
        CommandHandler("health", handler.handle_health),
        CommandHandler("job", handler.handle_job_info)
    ]