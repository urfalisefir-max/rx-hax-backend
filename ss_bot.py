import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, filters, ContextTypes
)
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
import io
import re
import hashlib

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Yeni Win SS Botu Tokeni
SS_BOT_TOKEN = "9148266048:AAF8nA5yYlWFbYWs-nfHQVXS0S3IGsa6h88"
HEDEF_KANAL = "@RXWINSS"

gonderilen_fotolar = set()

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        user = message.from_user
        gonderen = f"@{user.username}" if user.username else user.first_name

        if message.photo:
            photo = message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            downloaded_file = await file.download_as_bytearray()
            
            # Tekrar atılan fotoğrafları engelle
            foto_hash = hashlib.md5(downloaded_file).hexdigest()
            if foto_hash in gonderilen_fotolar:
                await message.reply_text("⚠️ Bu ekran görüntüsü daha önce paylaşıldı!")
                return

            orijinal_gorsel = io.BytesIO(downloaded_file)

            # OCR İşlemleri
            image_stream = io.BytesIO(downloaded_file)
            img = Image.open(image_stream).convert("L")
            img = img.resize((img.width * 2, img.height * 2), Image.Resampling.BICUBIC)

            enhancer = ImageEnhance.Contrast(img)
            img_contrast = enhancer.enhance(2.0)

            metin1 = pytesseract.image_to_string(img_contrast, config="--psm 3")
            metin2 = pytesseract.image_to_string(img_contrast, config="--psm 11")
            metin3 = pytesseract.image_to_string(ImageOps.invert(img_contrast), config="--psm 11")
            metin4 = pytesseract.image_to_string(img, config="--psm 6")

            ham_metin = (metin1 + "\n" + metin2 + "\n" + metin3 + "\n" + metin4).lower()
            temiz_metin = re.sub(r'[^a-z0-9]', '', ham_metin)

            # 1. Kural: @RX_HAX etiketi zorunlu
            etiket_var = "rxhax" in temiz_metin

            # 2. Kural: Montaj/rastgele fotoğraf eleme (Oyun içi terim kontrolü)
            # Fotoğrafın gerçekten bir oyun/zafer ekranı olduğunu doğrulamak için anahtar kelimeler arıyoruz
            oyun_terimleri = ["victory", "winner", "chicken", "mvp", "rank", "kill", "match", "game", "top", "savas", "kazandi"]
            oyun_ekrani_mi = any(terim in ham_metin for terim in oyun_terimleri)

            if not etiket_var:
                await message.reply_text("❌ Ekran görüntüsünde `@RX_HAX` etiketi okunamadı!")
                return

            if not oyun_ekrani_mi:
                await message.reply_text("❌ Bu ekran geçerli bir oyun zafer/MVP ekranı olarak algılanmadı! Lütfen orijinal oyun içi ekran görüntüsü atın.")
                return

            # Her iki şart da sağlanırsa kanala ilet
            gonderilen_fotolar.add(foto_hash)
            caption_text = (
                f"🎯 **Yeni Win / MVP SS Tespit Edildi!**\n\n"
                f"👤 **Gönderen:** {gonderen}\n"
                f"🔍 **Durum:** Etiket ve Oyun Ekranı Doğrulandı!"
            )
            await context.bot.send_photo(
                chat_id=HEDEF_KANAL,
                photo=orijinal_gorsel,
                caption=caption_text,
                parse_mode="Markdown"
            )
            await message.reply_text("✅ Ekran görüntün doğrulandı ve kanala iletildi!")

    except Exception as e:
        print(f"Hata detayı: {e}")
        await message.reply_text(f"⚠️ İşlem sırasında hata oluştu: {e}")

def main():
    app = ApplicationBuilder().token(SS_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_media))

    print("Win SS Botu Aktif ve Koruma Modunda!")
    app.run_polling()

if __name__ == "__main__":
    main()
