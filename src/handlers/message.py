import re
from telegram import Update
from telegram.ext import ContextTypes
from handlers.instagram import download_instagram_content

INSTAGRAM_URL_PATTERN = re.compile(r"https?://(www\.)?instagram\.com/[\w\-./?=&%]+", re.IGNORECASE)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text or ""
    # If it's a command, ignore (handled elsewhere)
    if message.startswith("/"):
        return
    # Detect Instagram URL
    match = INSTAGRAM_URL_PATTERN.search(message)
    if match:
        url = match.group(0)
        result = download_instagram_content(url)
        await update.message.reply_text(result)
    # Ignore all other messages
