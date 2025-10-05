from telegram import Update
from telegram.ext import ContextTypes
from handlers.instagram import download_instagram_content

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide an Instagram URL. Usage: /download <url>")
        return
    url = context.args[0]
    result = download_instagram_content(url)
    await update.message.reply_text(result)
