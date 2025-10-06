from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import get_bot_token

from handlers.start import start
from handlers.message import handle_message
from handlers.session import get_session_conversation_handler
from handlers.download import get_download_handlers
from handlers.report import get_report_handlers

def main():
    # Set up logging
    from logger import setup_logging, get_logger
    setup_logging()
    logger = get_logger("bot")
    
    try:
        # Create necessary directories
        from utils.constants import SESSIONS_DIR, DOWNLOADS_DIR, JOB_BASE_DIR
        import os
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(JOB_BASE_DIR, exist_ok=True)
        
        # Initialize services
        from utils.service_manager import service_manager
        from utils.state_tracker import StateTracker
        from utils.reporting import ReportingSystem
        from handlers.download import DownloadHandler
        from handlers.upload import UploadHandler
        
        state_tracker = StateTracker()
        reporting_system = ReportingSystem()
        download_handler = DownloadHandler()
        upload_handler = UploadHandler()
        
        # Initialize bot application
        app = ApplicationBuilder().token(get_bot_token()).build()
        
        # Register handlers in order of precedence
        handlers = [
            CommandHandler("start", start),
            get_session_conversation_handler(),
            *get_download_handlers(),  # Unpack download handlers
            *get_report_handlers(),  # Unpack reporting handlers
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ]
        
        for handler in handlers:
            app.add_handler(handler)
            
        logger.info("Bot is running. Press Ctrl+C to stop.")
        app.run_polling()
        
    except Exception as e:
        logger.exception("Fatal error in main loop")

if __name__ == "__main__":
    main()
