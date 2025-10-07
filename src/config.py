import os

def get_bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    
def get_admin_chat_id():
    """Get the Telegram chat ID for admin notifications."""
    return os.getenv("TELEGRAM_ADMIN_CHAT_ID", "YOUR_ADMIN_CHAT_ID_HERE")
