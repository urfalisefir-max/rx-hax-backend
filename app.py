import os
import sqlite3
import threading
from io import BytesIO
from flask import Flask, jsonify, request
from PIL import Image
import pytesseract
import telebot

app = Flask(__name__)

# Bot Token ve Veritabanı Yapılandırması
TOKEN = os.environ.get(
    "BOT_TOKEN", "BURAYA_BOT_TOKEN_YAZ"
)  # Token'ı buraya yazabilirsin
bot = telebot.TeleBot(TOKEN)
DB_PATH = "keys.db"


def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      """CREATE TABLE IF NOT EXISTS keys (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      key_text TEXT UNIQUE,
                      status TEXT DEFAULT 'active'
                  )"""
  )
  conn.commit()
  conn.close()


def download_db_from_github():
  init_db()
  print("Veritabanı ve tablolar hazır.")


# --- TELEGRAM BOT KOMUTLARI VE İŞLEMLERİ ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
  bot.reply_to(
      message,
      "🛡️ **RX-HAX Lisans & Win SS Botu** aktif ve çalışıyor! 🚀",
      parse_mode="Markdown",
  )


# Win SS / OCR ile Gelen Fotoğrafları Denetleme Modülü
@bot.message_handler(content_types=["photo"])
def handle_win_ss(message):
  try:
    # Kullanıcının gönderdiği fotoğrafı indir
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file)

    image = Image.open(BytesIO(downloaded_file))
    text = pytesseract.image_to_string(image).lower()

    # OCR ile görselden metin okuma ve filtreleme
    print(f"OCR Okunan Metin: {text[:100]}...")

    # Örnek otomatik moderasyon veya filtre mantığını buraya ekleyebilirsin
  except Exception as e:
    print(f"OCR İşlem Hatası: {e}")


# --- BOTU ARKA PLANDA ÇALIŞTIRAN THREAD ---
def run_bot():
  try:
    print("🛡️ Telegram Bot Arka Planda Başlatılıyor...")
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
  except Exception as e:
    print(f"Bot polling hatası: {e}")


# Gunicorn (Render) modül olarak içe aktardığında botun arka planda çalışmasını sağlar
if not os.environ.get("BOT_RUNNING"):
  os.environ["BOT_RUNNING"] = "true"
  download_db_from_github()

  bot_thread = threading.Thread(target=run_bot)
  bot_thread.daemon = True
  bot_thread.start()


# --- FLASK WEB ROTALARI & LİSANS API ---
@app.route("/")
def home():
  return "RX-HAX Backend Aktif ve Çalışıyor!"


@app.route("/api/check")
def api_check():
  key = request.args.get("key", "")
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute("SELECT status FROM keys WHERE key_text = ?", (key,))
  result = cursor.fetchone()
  conn.close()

  if result:
    return jsonify({"status": "success", "key_status": result[0]})
  return jsonify({"status": "error", "message": "Key bulunamadı"})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
  