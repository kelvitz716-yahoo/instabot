from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from config import get_bot_token

from handlers.start import start
from handlers.message import handle_message
from handlers.message import handle_message

def main():
    app = ApplicationBuilder().token(get_bot_token()).build()
    app.add_handler(CommandHandler("start", start))
    # /download command removed; now only /start and message handler

    # Handle all non-command messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
