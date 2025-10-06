from telegram import Update
from telegram.ext import ContextTypes
from utils.ui_helper import format_help_message

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler - shows welcome message and help"""
    welcome_msg = (
        "👋 Welcome to Instagram Downloader Bot!\n\n"
        "I can help you download content from Instagram. "
        "Simply send me any Instagram URL and I'll handle the rest.\n\n"
        "Here's a quick guide to get started:"
    )
    await update.message.reply_text(welcome_msg)
    await update.message.reply_text(format_help_message())
