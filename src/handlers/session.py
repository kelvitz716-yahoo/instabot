from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from logger import get_logger
from utils.constants import (
    SESSIONS_DIR, COOKIES_PATH, HELP_SESSION_LOAD, 
    REQUIRED_COOKIE_STRINGS
)
from utils.file_handler import ensure_dir, validate_file_content
from utils.telegram_helper import reply_with_error

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
    
    # Validate file content
    valid, error_msg = validate_file_content(COOKIES_PATH, REQUIRED_COOKIE_STRINGS)
    
    if valid:
        await update.message.reply_text(
            "Cookies file uploaded and validated successfully! "
            "Instagram downloads will now use this session."
        )
        logger.info("Valid Instagram cookies.txt uploaded and saved.")
    else:
        await reply_with_error(
            update, context,
            f"Cookie validation failed: {error_msg}. Please try again.",
            f"Invalid cookies.txt uploaded: {error_msg}"
        )
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
