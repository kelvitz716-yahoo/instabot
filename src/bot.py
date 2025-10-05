from telegram.ext import ApplicationBuilder, CommandHandler
from config import get_bot_token
from handlers.start import start

def main():
    app = ApplicationBuilder().token(get_bot_token()).build()
    app.add_handler(CommandHandler("start", start))
    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
