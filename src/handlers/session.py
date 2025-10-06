import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from logger import get_logger
from utils.constants import (
    SESSIONS_DIR, COOKIES_PATH, HELP_SESSION_LOAD
)
from utils.file_handler import ensure_dir
from utils.telegram_helper import reply_with_error
from utils.instagram_validator import validate_instagram_session

ASK_UPLOAD = 1
logger = get_logger("handlers.session")

async def session_load(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the cookie upload process"""
    await update.message.reply_text(HELP_SESSION_LOAD)
    return ASK_UPLOAD

async def receive_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded cookies.txt file"""
    if not update.message.document:
        await reply_with_error(update, context, "No file detected. Please upload your cookies.txt file.")
        return ASK_UPLOAD
        
    file = update.message.document
    if not file.file_name.endswith(".txt"):
        await reply_with_error(update, context, "File must be named cookies.txt.")
        return ASK_UPLOAD
        
    # Download file
    ensure_dir(SESSIONS_DIR)
    tg_file = await file.get_file()
    await tg_file.download_to_drive(COOKIES_PATH)
    
    # Validate Instagram session
    valid, error_msg = validate_instagram_session(COOKIES_PATH)
    
    if valid:
        await update.message.reply_text(
            "✅ Session validated successfully! Your Instagram cookies are working.\n"
            "You can now use the bot to download Instagram content."
        )
        logger.info("Valid Instagram session validated and saved.")
    else:
        await reply_with_error(
            update, context,
            f"❌ Session validation failed: {error_msg}\n"
            "Please make sure your cookies are fresh and try again.",
            f"Instagram session validation failed: {error_msg}"
        )
        # Clean up invalid cookie file
        try:
            os.remove(COOKIES_PATH)
        except:
            pass
        return ASK_UPLOAD
        
    return ConversationHandler.END

def get_session_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler("session_load", session_load)],
        states={
            ASK_UPLOAD: [MessageHandler(filters.Document.ALL, receive_cookies)]
        },
        fallbacks=[],
        allow_reentry=True
    )
