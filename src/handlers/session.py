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
    help_message = (
        "📤 Upload Instagram Cookie File\n"
        "════════════════════════\n\n"
        "🕒 You have 30 seconds to send your cookies.txt file.\n\n"
        "📝 Instructions:\n"
        "1️⃣ Use a cookie exporter extension:\n"
        "   • 'Export Cookies' or\n"
        "   • 'Cookie Quick Manager'\n\n"
        "2️⃣ On Instagram website:\n"
        "   • Make sure you're logged in\n"
        "   • Export cookies to file\n\n"
        "3️⃣ Send the file here\n\n"
        "⚠️ Important:\n"
        "• File must be named 'cookies.txt'\n"
        "• Must contain Instagram cookies\n"
        "• Must be fresh (recent export)\n\n"
        "⏳ Waiting for file..."
    )
    await update.message.reply_text(help_message)
    return ASK_UPLOAD

async def receive_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded cookies.txt file"""
    if not update.message.document:
        error_msg = (
            "❌ No file received\n"
            "════════════════\n\n"
            "Please send a cookies.txt file.\n"
            "Type /session_load to try again."
        )
        await update.message.reply_text(error_msg)
        return ASK_UPLOAD
        
    file = update.message.document
    if not file.file_name.endswith(".txt"):
        error_msg = (
            "❌ Invalid File Format\n"
            "═══════════════════\n\n"
            "File must be named 'cookies.txt'\n"
            "Current file: " + file.file_name + "\n\n"
            "Please export cookies in the correct format.\n"
            "Type /session_load to try again."
        )
        await update.message.reply_text(error_msg)
        return ASK_UPLOAD
        
    # Download file
    ensure_dir(SESSIONS_DIR)
    tg_file = await file.get_file()
    await tg_file.download_to_drive(COOKIES_PATH)
    
    # Validate Instagram session
    valid, error_msg = validate_instagram_session(COOKIES_PATH)
    
    status_msg = await update.message.reply_text("🔄 Validating session...")
    
    if valid:
        success_msg = (
            "✅ Session Validated Successfully!\n"
            "═══════════════════════════\n\n"
            "🔐 Login Status: Active\n"
            "📅 Validated: Just now\n"
            "⌛ Expires: 30 days\n\n"
            "You can now:\n"
            "• Download stories\n"
            "• Access private content\n"
            "• Download highlights\n\n"
            "Try sending an Instagram URL!"
        )
        await status_msg.edit_text(success_msg)
        logger.info("Valid Instagram session validated and saved")
    else:
        error_msg = (
            "❌ Session Validation Failed\n"
            "═══════════════════════\n\n"
            f"Error: {error_msg}\n\n"
            "Common issues:\n"
            "• Expired cookies\n"
            "• Invalid format\n"
            "• Missing required cookies\n\n"
            "Please try again with fresh cookies.\n"
            "Type /session_load to restart."
        )
        await status_msg.edit_text(error_msg)
        logger.warning(f"Session validation failed: {error_msg}")
        
        # Clean up invalid cookie file
        try:
            os.remove(COOKIES_PATH)
        except:
            pass
        return ASK_UPLOAD
        
    return ConversationHandler.END

async def session_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check Instagram session status"""
    if os.path.exists(COOKIES_PATH):
        valid, _ = validate_instagram_session(COOKIES_PATH)
        if valid:
            msg = (
                "🔐 Session Status\n"
                "═══════════════\n\n"
                "✅ Active & Working\n"
                "📅 Last Check: Just now\n"
                "🔓 Access: Full\n\n"
                "You have access to:\n"
                "• Private content\n"
                "• Stories\n"
                "• Highlights\n"
                "• Saved posts"
            )
        else:
            msg = (
                "🔐 Session Status\n"
                "═══════════════\n\n"
                "❌ Session Invalid\n"
                "⚠️ Needs Renewal\n\n"
                "Please use /session_load\n"
                "to upload new cookies."
            )
    else:
        msg = (
            "🔐 Session Status\n"
            "═══════════════\n\n"
            "⚠️ No Active Session\n\n"
            "Use /session_load to login\n"
            "and access private content."
        )
    
    await update.message.reply_text(msg)

def get_session_conversation_handler():
    return ConversationHandler(
        entry_points=[
            CommandHandler("session_load", session_load),
            CommandHandler("session_status", session_status)
        ],
        states={
            ASK_UPLOAD: [MessageHandler(filters.Document.ALL, receive_cookies)]
        },
        fallbacks=[],
        allow_reentry=True
    )
