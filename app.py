import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
import sqlite3
import pytesseract
from PIL import Image, ImageEnhance, ImageOps
import io
import re
import hashlib
from aiohttp import web

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

TOKEN = "9009112136:AAFmLQrTB1u3InEw2vyX4sYGmdKPR_F_u1c"
HEDEF_KANAL = "@RXWINSS"

# Veritabanı (keys.db) Kurulumu
def init_db():
    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_text TEXT UNIQUE,
            duration TEXT,
            device_limit INTEGER,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()
gonderilen_fotolar = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Key Yönetimi", callback_data="key_menu")],
        [InlineKeyboardButton("📊 Bot Durumu", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔑 **RX HAX Yönetim Paneline Hoş Geldin ROXY!**\n\n"
        "Hızlıca key eklemek için şu formatı kullanabilirsin:\n"
        "`/addkey [Key] [Süre] [Cihaz Sınırı]`\n\n"
        "Örnek: `/addkey RX-VIP-99 30 Gün 100`",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def addkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "⚠️ **Eksik Bilgi!**\n\n"
            "Örnek kullanım şekli:\n"
            "`/addkey RX-VIP-99 30 Gün 100`",
            parse_mode="Markdown"
        )
        return

    key_text = args[0]
    # Süre ve cihaz sınırını doğru ayırabilmek için son parametre cihaz sınırıdır
    device_limit = args[-1]
    duration = " ".join(args[1:-1])

    try:
        device_limit_int = int(device_limit)
    except ValueError:
        await update.message.reply_text("⚠️ Cihaz sınırı sayı olmalıdır! Örn: `100`", parse_mode="Markdown")
        return

    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO keys (key_text, duration, device_limit, status) VALUES (?, ?, ?, ?)", 
                       (key_text, duration, device_limit_int, "Aktif"))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()

    if success:
        await update.message.reply_text(
            f"🎉 **Key Başarıyla Oluşturuldu!**\n\n"
            f"🔑 Key: `{key_text}`\n"
            f"⏱ Süre: {duration}\n"
            f"📱 Cihaz Sınırı: {device_limit_int}\n"
            f"🟢 Durum: Aktif",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Bu key zaten veritabanında kayıtlı!")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "key_menu":
        await query.edit_message_text(
            "🔑 **Key Ekleme Rehberi**\n\n"
            "Sohbete komut yazarak anında key oluşturabilirsin:\n"
            "`/addkey [Key] [Süre] [Cihaz Sınırı]`\n\n"
            "Örnek:\n"
            "`/addkey RX-TEST-1 7 Gün 250`",
            parse_mode="Markdown"
        )
    elif query.data == "status":
        await query.answer("Sistemler aktif ve stabil çalışıyor!", show_alert=True)

# Win SS Kontrolü
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        if not message or not message.photo:
            return

        user = message.from_user
        gonderen = f"@{user.username}" if user.username else user.first_name

        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        downloaded_file = await file.download_as_bytearray()
        
        foto_hash = hashlib.md5(downloaded_file).hexdigest()
        if foto_hash in gonderilen_fotolar:
            await message.reply_text("⚠️ Bu ekran görüntüsü daha önce paylaşıldı!")
            return

        orijinal_gorsel = io.BytesIO(downloaded_file)

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

        etiket_var = "rxhax" in temiz_metin
        oyun_terimleri = ["victory", "winner", "chicken", "mvp", "rank", "kill", "match", "game", "top", "savas", "kazandi"]
        oyun_ekrani_mi = any(terim in ham_metin for terim in oyun_terimleri)

        if not etiket_var:
            await message.reply_text("❌ Ekran görüntüsünde `@RX_HAX` etiketi okunamadı!")
            return

        if not oyun_ekrani_mi:
            await message.reply_text("❌ Bu ekran geçerli bir oyun zafer/MVP ekranı olarak algılanmadı!")
            return

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

async def web_server(request):
    return web.Response(text="RX HAX Bot is running!")

async def start_web_server():
    app_web = web.Application()
    app_web.add_routes([web.get('/', web_server)])
    runner = web.AppRunner(app_web)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await start_web_server()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addkey", addkey_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_media))

    print("RX HAX Kararlı Sistem Aktif!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    import asyncio
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
