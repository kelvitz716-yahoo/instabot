from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from telegram import Update
from config import get_bot_token

from handlers.start import start
from handlers.message import handle_message
from handlers.session import get_session_conversation_handler
from handlers.download import get_download_handlers
from handlers.report import get_report_handlers
from handlers.status import status

async def setup_services():
    """Initialize all services and perform recovery operations."""
    from logger import setup_logging, get_logger
    setup_logging()
    logger = get_logger("bot")
    
    # Create necessary directories
    from utils.constants import SESSIONS_DIR, DOWNLOADS_DIR, JOB_BASE_DIR
    import os
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    os.makedirs(JOB_BASE_DIR, exist_ok=True)
    
    # Initialize services
    from utils.service_init import initialize_services
    from utils.job_monitor import JobMonitor
    from handlers.download import DownloadHandler
    from handlers.upload import UploadHandler
    
    try:
        # Initialize core services in proper order
        logger.info("Initializing services...")
        services = initialize_services()
        job_manager = services['job_manager']
        job_monitor = JobMonitor()
        
        # Initialize handlers
        download_handler = DownloadHandler()
        upload_handler = UploadHandler()
        
        # Check for and recover interrupted jobs
        logger.info("Scanning for interrupted jobs...")
        interrupted_jobs = await services['recovery_system'].scan_for_interrupted_jobs()
        if interrupted_jobs:
            logger.info(f"Found {len(interrupted_jobs)} interrupted jobs. Attempting recovery...")
            for job_state in interrupted_jobs:
                if await services['recovery_system'].resume_job(job_state):
                    logger.info(f"Successfully recovered job {job_state.job_id}")
                else:
                    logger.error(f"Failed to recover job {job_state.job_id}")
        
        # Return the job monitor for starting later
        return job_monitor, logger
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise

def run():
    """Run the bot with proper exception handling"""
    import asyncio
    from logger import get_logger
    
    logger = get_logger("bot")
    
    async def run_app():
        """Run the Telegram bot application"""
        app = ApplicationBuilder().token(get_bot_token()).build()
        
        # Register handlers in order of precedence
        handlers = [
            CommandHandler("start", start),
            CommandHandler("status", status),
            get_session_conversation_handler(),
            *get_download_handlers(),
            *get_report_handlers(),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ]
        
        for handler in handlers:
            app.add_handler(handler)
            
        # Initialize the application
        await app.initialize()
        
        # Start polling
        await app.start()
        await app.updater.start_polling()
        
        # Return app for cleanup
        return app
    
    async def main():
        """Main async function coordinating bot and job monitor"""
        try:
            # Initialize services - use job_monitor but ignore logger since we already have one
            job_monitor, _ = await setup_services()
            
            # Start the bot application
            app = await run_app()
            
            # Start job monitoring
            monitor_task = asyncio.create_task(job_monitor.start_monitoring())
            
            logger.info("Bot is running with job monitoring. Press Ctrl+C to stop.")
            
            # Keep the main task running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                # Handle shutdown
                await app.stop()
                await app.updater.stop()
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            logger.exception("Fatal error in main loop")
            raise
    
    # Run the async main function
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception("Fatal error in main loop")
        raise

if __name__ == "__main__":
    run()
