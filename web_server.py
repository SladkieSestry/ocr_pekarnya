from flask import Flask
import os
import threading
from bot import main as run_bot

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running! 🚀"

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}

def run_bot_thread():
    """Запуск бота в окремому потоці"""
    run_bot()

if __name__ == '__main__':
    # Запускаємо бота в окремому потоці
    bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
    bot_thread.start()
    
    # Запускаємо веб-сервер
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)