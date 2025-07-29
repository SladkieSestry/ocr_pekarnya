import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token - беремо з змінних середовища Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "7940729582:AAHFGzrVxYLZT8VWZ90xHgJD6RF0OvK0jTs")

# Налаштування для групування фото
PHOTO_GROUPING_TIMEOUT = 300  # 5 хвилин в секундах 