import os
import threading
import telebot
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
import io
import re
import hashlib
from flask import Flask, request, jsonify

# --- FLASK SUNUCU (Auth Sistemi İçin) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "RX-HAX Backend Aktif ve Çalışıyor! 🚀"

# Örnek Auth endpoint'i (kendi auth kodunu buraya entegre edebilirsin)
@app.route('/api/check', methods=['GET', 'POST'])
def check_key():
    key = request.args.get('key') or (request.json and request.json.get('key'))
    # Burada keys.db kontrolü yapılır
    return jsonify({"status": "success", "message": "Key aktif"})


# --- TELEGRAM WIN SS & TROLL KORUMA BOTU ---
TOKEN = "9148266048:AAGupZmFeSO22C6ZjbZ0fFgZgydNC8Iya2U"
HEDEF_KANAL = "@RXWINSS"

bot = telebot.TeleBot(TOKEN)
KARA_LISTE = ["ravix_op", "yilanpeker"]
gonderilen_fotolar = set()

def kara_liste_kontrol(message):
    try:
        if message.from_user and message.from_user.username:
            username = message.from_user.username.lower()
            if username in KARA_LISTE:
                chat_id = message.chat.id
                user_id = message.from_user.id
                bot.delete_message(chat_id, message.message_id)
                bot.ban_chat_member(chat_id, user_id)
                return True
    except Exception as e:
        print(f"Banlama hatası: {e}")
    return False

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if kara_liste_kontrol(message):
        return
    try:
        gonderen = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        foto_hash = hashlib.md5(downloaded_file).hexdigest()
        if foto_hash in gonderilen_fotolar:
            bot.reply_to(message, "⚠️ Bu ekran görüntüsü daha önce zaten paylaşıldı!")
            return

        orijinal_gorsel = io.BytesIO(downloaded_file)
        img = Image.open(io.BytesIO(downloaded_file)).convert("L")
        img = img.resize((img.width * 2, img.height * 2), Image.Resampling.BICUBIC)
        
        enhancer = ImageEnhance.Contrast(img)
        img_contrast = enhancer.enhance(2.0)
        
        metin1 = pytesseract.image_to_string(img_contrast, config="--psm 3")
        metin2 = pytesseract.image_to_string(img_contrast, config="--psm 11")
        metin3 = pytesseract.image_to_string(ImageOps.invert(img_contrast), config="--psm 11")
        metin4 = pytesseract.image_to_string(img, config="--psm 6")
        
        ham_metin = (metin1 + "\n" + metin2 + "\n" + metin3 + "\n" + metin4).lower()
        temiz_metin = re.sub(r'[^a-z0-9]', '', ham_metin)

        if "rxhax" in temiz_metin:
            gonderilen_fotolar.add(foto_hash)
            caption_text = f"🎯 Yeni Win / MVP SS Tespit Edildi!\n\n👤 Gönderen: {gonderen}\n🔍 Etiket Doğrulandı: @RX_HAX"
            bot.send_photo(HEDEF_KANAL, orijinal_gorsel, caption=caption_text)
            bot.reply_to(message, "✅ Etiket doğrulandı, kanala iletildi!")
        else:
            bot.reply_to(message, "❌ Reddedildi: Görselin içerisinde 'RX HAX' etiketi okunamadı!")
    except Exception as e:
        print(f"Hata detayı: {e}")

@bot.message_handler(content_types=['video'])
def handle_video(message):
    if kara_liste_kontrol(message):
        return
    bot.reply_to(message, "❌ Güvenlik nedeniyle videolu paylaşımlar otomatik kapatılmıştır!")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    kara_liste_kontrol(message)

def run_bot():
    print("🛡️ Telegram Bot Arka Planda Başlatılıyor...")
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    # Botu ayrı bir thread (arkaplanda çalışan iş parçacığı) içinde başlatıyoruz
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

    # Flask sunucusunu Render'ın verdiği port üzerinden başlatıyoruz
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
