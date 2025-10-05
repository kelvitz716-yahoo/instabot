from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import get_bot_token

from handlers.start import start
from handlers.message import handle_message
from handlers.session import get_session_conversation_handler
from handlers.download import get_download_handlers

def main():
    from logger import get_logger
    logger = get_logger("bot")
    try:
        app = ApplicationBuilder().token(get_bot_token()).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(get_session_conversation_handler())
        
        # Add download-related handlers
        for handler in get_download_handlers():
            app.add_handler(handler)
            
        # Add general message handler last
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logger.info("Bot is running. Press Ctrl+C to stop.")
        app.run_polling()
    except Exception as e:
        logger.exception("Fatal error in main loop")

if __name__ == "__main__":
    main()
