import os
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from logger import get_logger

SESSIONS_DIR = "/app/sessions"
COOKIES_FILENAME = "cookies.txt"

ASK_UPLOAD = 1

async def session_load(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please upload your Instagram cookies.txt file.\n"
        "Instructions: Export your Instagram cookies using the browser extension 'Get cookies.txt' and upload the file here."
    )
    return ASK_UPLOAD

async def receive_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger = get_logger("handlers.session")
    if not update.message.document:
        await update.message.reply_text("No file detected. Please upload your cookies.txt file.")
        return ASK_UPLOAD
    file = update.message.document
    if not file.file_name.endswith(".txt"):
        await update.message.reply_text("File must be named cookies.txt.")
        return ASK_UPLOAD
    # Download file
    file_path = os.path.join(SESSIONS_DIR, COOKIES_FILENAME)
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    tg_file = await file.get_file()
    await tg_file.download_to_drive(file_path)
    # Validate file (basic check: not empty)
    if os.path.getsize(file_path) == 0:
        await update.message.reply_text("Uploaded file is empty. Please try again.")
        return ASK_UPLOAD
    # Validate cookies.txt content for Instagram sessionid and ds_user_id
    with open(file_path, "r") as f:
        content = f.read()
    valid = ("sessionid" in content and "ds_user_id" in content)
    if valid:
        await update.message.reply_text("Cookies file uploaded and validated successfully! Instagram downloads will now use this session.")
        logger.info("Valid Instagram cookies.txt uploaded and saved.")
    else:
        await update.message.reply_text("Cookies file uploaded but does not appear valid for Instagram (missing sessionid or ds_user_id). Please try again.")
        logger.warning("Invalid cookies.txt uploaded: missing sessionid or ds_user_id.")
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
