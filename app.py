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
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {}
    
    keyboard = [
        [InlineKeyboardButton("➕ Key Ekle (Add Key)", callback_data="add_key")],
        [InlineKeyboardButton("❄️ Key Dondur / Çöz", callback_data="freeze_key")],
        [InlineKeyboardButton("🗑️ Key Sil", callback_data="delete_key")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("🔑 **Key Yönetim Paneli**\n\nYapmak istediğin işlemi seç:", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if user_id not in user_states:
        user_states[user_id] = {}

    if data == "main_menu":
        user_states[user_id] = {}
        keyboard = [
            [InlineKeyboardButton("➕ Key Ekle (Add Key)", callback_data="add_key")],
            [InlineKeyboardButton("❄️ Key Dondur / Çöz", callback_data="freeze_key")],
            [InlineKeyboardButton("🗑️ Key Sil", callback_data="delete_key")]
        ]
        await query.edit_message_text("🔑 **Key Yönetim Paneli**\n\nYapmak istediğin işlemi seç:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "add_key":
        user_states[user_id] = {"step": "waiting_key_text"}
        keyboard = [[InlineKeyboardButton("🔙 İptal / Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text(
            "✍️ Lütfen eklemek istediğin **Key (Lisans) metnini** yaz ve gönder:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("durum_"):
        sure = data.replace("durum_", "")
        if sure == "custom":
            user_states[user_id]["step"] = "waiting_custom_duration"
            keyboard = [[InlineKeyboardButton("🔙 İptal", callback_data="main_menu")]]
            await query.edit_message_text("⏱️ Lütfen kaç gün olacağını klavyeden sayı olarak yaz (Örn: 45):", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        user_states[user_id]["duration"] = sure
        user_states[user_id]["step"] = "waiting_device_limit"
        
        keyboard = [
            [InlineKeyboardButton("100 Cihaz", callback_data="cihaz_100")],
            [InlineKeyboardButton("250 Cihaz", callback_data="cihaz_250")],
            [InlineKeyboardButton("500 Cihaz", callback_data="cihaz_500")],
            [InlineKeyboardButton("1000 Cihaz", callback_data="cihaz_1000")],
            [InlineKeyboardButton("✏️ Manuel Cihaz Gir", callback_data="cihaz_custom")],
            [InlineKeyboardButton("🔙 İptal", callback_data="main_menu")]
        ]
        await query.edit_message_text("📱 Şimdi de **Cihaz Sınırını** seç veya manuel gir:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("cihaz_"):
        cihaz_secim = data.replace("cihaz_", "")
        if cihaz_secim == "custom":
            user_states[user_id]["step"] = "waiting_custom_device"
            keyboard = [[InlineKeyboardButton("🔙 İptal", callback_data="main_menu")]]
            await query.edit_message_text("📱 Lütfen izin verilen cihaz sınırını sayı olarak yaz (Örn: 750):", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        user_states[user_id]["device_limit"] = int(cihaz_secim)
        await save_key_to_db(query, user_id)

    elif data == "freeze_key":
        keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text("❄️ Key dondurma ve çözme paneli yakında aktif olacaktır.", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "delete_key":
        keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
        await query.edit_message_text("🗑️ Key silme paneli yakında aktif olacaktır.", reply_markup=InlineKeyboardMarkup(keyboard))

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_states or "step" not in user_states[user_id]:
        return

    step = user_states[user_id]["step"]

    if step == "waiting_key_text":
        user_states[user_id]["key_text"] = text
        user_states[user_id]["step"] = "waiting_duration"
        
        keyboard = [
            [InlineKeyboardButton("1 Saat", callback_data="durum_1 Saat")],
            [InlineKeyboardButton("1 Gün", callback_data="durum_1 Gün")],
            [InlineKeyboardButton("7 Gün", callback_data="durum_7 Gün")],
            [InlineKeyboardButton("15 Gün", callback_data="durum_15 Gün")],
            [InlineKeyboardButton("30 Gün", callback_data="durum_30 Gün")],
            [InlineKeyboardButton("✏️ Özel Gün Sayısı Gir", callback_data="durum_custom")]
        ]
        await update.message.reply_text(f"✅ Key alındı: `{text}`\n\n⏱️ Şimdi **Süreyi** seç:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif step == "waiting_custom_duration":
        user_states[user_id]["duration"] = f"{text} Gün"
        user_states[user_id]["step"] = "waiting_device_limit"

        keyboard = [
            [InlineKeyboardButton("100 Cihaz", callback_data="cihaz_100")],
            [InlineKeyboardButton("250 Cihaz", callback_data="cihaz_250")],
            [InlineKeyboardButton("500 Cihaz", callback_data="cihaz_500")],
            [InlineKeyboardButton("1000 Cihaz", callback_data="cihaz_1000")],
            [InlineKeyboardButton("✏️ Manuel Cihaz Gir", callback_data="cihaz_custom")],
            [InlineKeyboardButton("🔙 İptal", callback_data="main_menu")]
        ]
        await update.message.reply_text(f"✅ Süre belirlendi: {text} Gün\n\n📱 Şimdi **Cihaz Sınırını** seç veya yaz:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif step == "waiting_custom_device":
        try:
            limit = int(text)
            user_states[user_id]["device_limit"] = limit
            await save_key_to_db_message(update, user_id)
        except ValueError:
            await update.message.reply_text("⚠️ Lütfen geçerli bir sayı gir!")

async def save_key_to_db(query, user_id):
    data = user_states.get(user_id, {})
    key_text = data.get("key_text")
    duration = data.get("duration")
    device_limit = data.get("device_limit")

    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO keys (key_text, duration, device_limit, status) VALUES (?, ?, ?, ?)", 
                       (key_text, duration, device_limit, "Aktif"))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()

    keyboard = [[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]]
    
    if success:
        await query.edit_message_text(
            f"🎉 **Key Başarıyla Oluşturuldu!**\n\n"
            f"🔑 Key: `{key_text}`\n"
            f"⏱ Süre: {duration}\n"
            f"📱 Cihaz Sınırı: {device_limit}\n"
            f"🟢 Durum: Aktif",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text("⚠️ Bu key zaten veritabanında kayıtlı!", reply_markup=InlineKeyboardMarkup(keyboard))
    
    user_states[user_id] = {}

async def save_key_to_db_message(update, user_id):
    data = user_states.get(user_id, {})
    key_text = data.get("key_text")
    duration = data.get("duration")
    device_limit = data.get("device_limit")

    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO keys (key_text, duration, device_limit, status) VALUES (?, ?, ?, ?)", 
                       (key_text, duration, device_limit, "Aktif"))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    conn.close()

    keyboard = [[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="main_menu")]]
    
    if success:
        await update.message.reply_text(
            f"🎉 **Key Başarıyla Oluşturuldu!**\n\n"
            f"🔑 Key: `{key_text}`\n"
            f"⏱ Süre: {duration}\n"
            f"📱 Cihaz Sınırı: {device_limit}\n"
            f"🟢 Durum: Aktif",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Bu key zaten veritabanında kayıtlı!", reply_markup=InlineKeyboardMarkup(keyboard))
    
    user_states[user_id] = {}

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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_media))

    print("RX HAX Tam Entegre Sistem Aktif!")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    import asyncio
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
