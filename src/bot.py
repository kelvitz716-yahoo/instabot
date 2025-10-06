from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import get_bot_token

from handlers.start import start
from handlers.message import handle_message
from handlers.session import get_session_conversation_handler
from handlers.download import get_download_handlers

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
        
        # Initialize bot application
        app = ApplicationBuilder().token(get_bot_token()).build()
        
        # Register handlers in order of precedence
        handlers = [
            CommandHandler("start", start),
            get_session_conversation_handler(),
            *get_download_handlers(),  # Unpack download handlers
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
