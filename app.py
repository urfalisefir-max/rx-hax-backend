import hashlib
import io
import os
import re
import sqlite3
import threading
import time
from flask import Flask, jsonify, request
from PIL import Image, ImageEnhance, ImageOps
import pytesseract
import requests
import telebot

app = Flask(__name__)

# --- TOKENLER VE AYARLAR ---
KEY_BOT_TOKEN = "9009112136:AAHpDw34EDBNEDbAprBM6MfMgQHoC90j6Oc"
WIN_BOT_TOKEN = "9148266048:AAGupZmFeSO22C6ZjbZ0fFgZgydNC8Iya2U"

key_bot = telebot.TeleBot(KEY_BOT_TOKEN)
win_bot = telebot.TeleBot(WIN_BOT_TOKEN)

DB_PATH = "keys.db"
HEDEF_KANAL = "@RXWINSS"
gonderilen_fotolar = set()


# Veritabanı Tablosu Oluşturma (Verileri silmeden korur)
def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  # Tablo varsa verileri silmez, sadece yoksa oluşturur
  cursor.execute(
      """CREATE TABLE IF NOT EXISTS keys (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      key_text TEXT UNIQUE,
                      status TEXT DEFAULT 'active'
                  )"""
  )
  conn.commit()
  conn.close()


# ==========================================
# 1. KEY YÖNETİM BOTU KODLARI (WTJKeyBot)
# ==========================================
@key_bot.message_handler(commands=["start"])
def key_bot_start(message):
  key_bot.reply_to(
      message,
      "🔑 **RX-HAX Key Yönetim Botuna** Hoş Geldin!\n\n"
      "Komutlar:\n"
      "/ekle <key> - Yeni lisans keyi ekler\n"
      "/sil <key> - Keyi siler\n"
      "/liste - Kayıtlı keyleri listeler",
      parse_mode="Markdown",
  )


@key_bot.message_handler(commands=["ekle"])
def add_key(message):
  try:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
      key_bot.reply_to(message, "⚠️ Kullanım: `/ekle <key-degeri>`")
      return
    new_key = parts[1].strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO keys (key_text, status) VALUES (?, 'active')",
        (new_key,),
    )
    conn.commit()
    conn.close()
    key_bot.reply_to(message, f"✅ Key başarıyla eklendi: `{new_key}`")
  except Exception as e:
    key_bot.reply_to(message, f"❌ Hata: {e}")


@key_bot.message_handler(commands=["sil"])
def delete_key(message):
  try:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
      key_bot.reply_to(message, "⚠️ Kullanım: `/sil <key-degeri>`")
      return
    target_key = parts[1].strip()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keys WHERE key_text = ?", (target_key,))
    conn.commit()
    conn.close()
    key_bot.reply_to(message, f"🗑️ Key silindi: `{target_key}`")
  except Exception as e:
    key_bot.reply_to(message, f"❌ Hata: {e}")


@key_bot.message_handler(commands=["liste"])
def list_keys(message):
  try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key_text FROM keys")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
      key_bot.reply_to(message, "📂 Veritabanında kayıtlı key bulunmuyor.")
      return

    key_list = "\n".join([f"• `{row[0]}`" for row in rows])
    key_bot.reply_to(
        message, f"📋 **Kayıtlı Keyler:**\n\n{key_list}", parse_mode="Markdown"
    )
  except Exception as e:
    key_bot.reply_to(message, f"❌ Hata: {e}")


# ==========================================
# 2. WİN SS / OCR FİLTRELEME BOTU (RXWINSS_BOT)
# ==========================================
@win_bot.message_handler(content_types=["photo", "video"])
def handle_media(message):
  try:
    gonderen = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else message.from_user.first_name
    )

    if message.content_type == "photo":
      file_info = win_bot.get_file(message.photo[-1].file_id)
      downloaded_file = win_bot.download_file(file_info.file_path)

      foto_hash = hashlib.md5(downloaded_file).hexdigest()
      if foto_hash in gonderilen_fotolar:
        win_bot.reply_to(message, "⚠️ Bu ekran görüntüsü daha önce paylaşıldı!")
        return

      orijinal_gorsel = io.BytesIO(downloaded_file)

      img = Image.open(io.BytesIO(downloaded_file)).convert("L")
      img = img.resize((img.width * 2, img.height * 2), Image.Resampling.BICUBIC)

      enhancer = ImageEnhance.Contrast(img)
      img_contrast = enhancer.enhance(2.0)

      metin1 = pytesseract.image_to_string(img_contrast, config="--psm 3")
      metin2 = pytesseract.image_to_string(img_contrast, config="--psm 11")
      metin3 = pytesseract.image_to_string(
          ImageOps.invert(img_contrast), config="--psm 11"
      )
      metin4 = pytesseract.image_to_string(img, config="--psm 6")

      ham_metin = (metin1 + "\n" + metin2 + "\n" + metin3 + "\n" + metin4).lower()
      temiz_metin = re.sub(r"[^a-z0-9]", "", ham_metin)

      etiket_var = "rxhax" in temiz_metin

      if etiket_var:
        gonderilen_fotolar.add(foto_hash)

        caption_text = (
            f"🎯 Yeni Win / MVP SS Tespit Edildi!\n\n"
            f"👤 Gönderen: {gonderen}\n"
            f"🔍 Etiket Doğrulandı: @RX_HAX"
        )
        win_bot.send_photo(HEDEF_KANAL, orijinal_gorsel, caption=caption_text)
        win_bot.reply_to(message, "✅ Etiket okundu, kanala iletildi!")
      else:
        win_bot.reply_to(message, "❌ RX HAX etiketi okunamadı!")

    elif message.content_type == "video":
      caption = message.caption.lower() if message.caption else ""

      if "rx" in caption and "hax" in caption:
        file_info = win_bot.get_file(message.video.file_id)
        downloaded_file = win_bot.download_file(file_info.file_path)
        orijinal_video = io.BytesIO(downloaded_file)

        caption_text = (
            f"🎥 Yeni Win Videosu Tespit Edildi!\n\n"
            f"👤 Gönderen: {gonderen}\n"
            f"🔍 Durum: Etiket Doğrulandı"
        )
        win_bot.send_video(HEDEF_KANAL, orijinal_video, caption=caption_text)
        win_bot.reply_to(message, "✅ Video kanala iletildi!")
      else:
        win_bot.reply_to(message, "❌ Açıklamaya @RX_HAX yazmalısın!")

  except Exception as e:
    print(f"Hata detayı: {e}")
    win_bot.reply_to(message, f"⚠️ Hata: {e}")


# ==========================================
# 3. THREAD'LER VE KENDİNİ UYANDIRMA (SELF-PING)
# ==========================================
def run_key_bot():
  try:
    print("🔑 Key Bot Başlatılıyor...")
    init_db()
    key_bot.infinity_polling(
        skip_pending=True, timeout=60, long_polling_timeout=60
    )
  except Exception as e:
    print(f"Key Bot Polling Hatası: {e}")


def run_win_bot():
  try:
    print("🛡️ Win SS Bot Başlatılıyor...")
    win_bot.infinity_polling(
        skip_pending=True, timeout=60, long_polling_timeout=60
    )
  except Exception as e:
    print(f"Win SS Bot Polling Hatası: {e}")


def self_ping():
  url = "https://rx-hax-backend.onrender.com"
  while True:
    try:
      time.sleep(240)  # Her 4 dakikada bir kendi adresine istek atar
      requests.get(url, timeout=10)
    except Exception:
      pass


if not os.environ.get("BOTS_RUNNING"):
  os.environ["BOTS_RUNNING"] = "true"
  threading.Thread(target=run_key_bot, daemon=Thread := True).start()
  threading.Thread(target=run_win_bot, daemon=True).start()
  threading.Thread(target=self_ping, daemon=True).start()


# ==========================================
# 4. FLASK WEB ROTALARI & LİSANS API
# ==========================================
@app.route("/")
def home():
  return "RX-HAX Backend & Multi-Bot Sistem Aktif!"


@app.route("/api/check")
def api_check():
  key = request.args.get("key", "").strip()
  if not key:
    return jsonify({"status": "error", "message": "Key parametresi eksik"})

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
