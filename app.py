import os
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# Bot Token'ı (Render Environment Variables üzerinden veya doğrudan buraya yazabilirsin)
TOKEN = os.getenv("TELEGRAM_TOKEN", "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")

# Konuşma Adımları
CHOOSING_DURATION, CUSTOM_DURATION, CHOOSING_DEVICE, CUSTOM_DEVICE = range(4)

# Veritabanı Kurulumu
def init_db():
    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            key_text TEXT PRIMARY KEY,
            duration TEXT,
            device_limit INTEGER,
            is_frozen INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# /start Komutu ve Ana Menü
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Key Ekle (Add Key)", callback_data="add_key")],
        [InlineKeyboardButton("❄️ Key Dondur / Çöz", callback_data="toggle_freeze")],
        [InlineKeyboardButton("🗑️ Key Sil", callback_data="delete_key")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("🔑 **Key Yönetim Paneli**", reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text("🔑 **Key Yönetim Paneli**", reply_markup=reply_markup, parse_mode="Markdown")

# Adım 1: Key Metnini Alma
async def start_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("Lütfen eklemek istediğiniz **Key** metnini yazın:")
    return CHOOSING_DURATION

# Adım 2: Süre Seçimi Menüsü
async def receive_key_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['key_text'] = update.message.text
    
    keyboard = [
        [InlineKeyboardButton("1 SAAT", callback_data="dur_1h"), InlineKeyboardButton("1 GÜN", callback_data="dur_1d")],
        [InlineKeyboardButton("7 GÜN", callback_data="dur_7d"), InlineKeyboardButton("15 GÜN", callback_data="dur_15d")],
        [InlineKeyboardButton("30 GÜN", callback_data="dur_30d")],
        [InlineKeyboardButton("✏️ Manuel Gün Gir", callback_data="dur_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Key: `{context.user_data['key_text']}`\n\nLütfen **Süre** seçin:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return CHOOSING_DEVICE

# Özel Süre Girme İsteği
async def custom_duration_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Lütfen geçerli gün sayısını sayı olarak yazın (Örn: 45):")
    return CUSTOM_DURATION

async def receive_custom_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['duration'] = f"{update.message.text} GÜN"
    
    # Cihaz Sınırı Menüsüne Geçiş
    keyboard = [
        [InlineKeyboardButton("100 CİHAZ", callback_data="dev_100"), InlineKeyboardButton("250 CİHAZ", callback_data="dev_250")],
        [InlineKeyboardButton("500 CİHAZ", callback_data="dev_500"), InlineKeyboardButton("1000 CİHAZ", callback_data="dev_1000")],
        [InlineKeyboardButton("✏️ Manuel Cihaz Sınırı Gir", callback_data="dev_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Key: `{context.user_data['key_text']}`\nSüre: {context.user_data['duration']}\n\nLütfen **Cihaz Sınırı** seçin:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return CHOOSING_DEVICE

# Adım 3: Cihaz Sınırı Menüsü (Buton ile gelen)
async def duration_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    dur_map = {
        "dur_1h": "1 SAAT", "dur_1d": "1 GÜN", 
        "dur_7d": "7 GÜN", "dur_15d": "15 GÜN", "dur_30d": "30 GÜN"
    }
    context.user_data['duration'] = dur_map[query.data]
    
    keyboard = [
        [InlineKeyboardButton("100 CİHAZ", callback_data="dev_100"), InlineKeyboardButton("250 CİHAZ", callback_data="dev_250")],
        [InlineKeyboardButton("500 CİHAZ", callback_data="dev_500"), InlineKeyboardButton("1000 CİHAZ", callback_data="dev_1000")],
        [InlineKeyboardButton("✏️ Manuel Cihaz Sınırı Gir", callback_data="dev_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Key: `{context.user_data['key_text']}`\nSüre: {context.user_data['duration']}\n\nLütfen **Cihaz Sınırı** seçin:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return CHOOSING_DEVICE

# Özel Cihaz Sınırı İsteği
async def custom_device_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Lütfen cihaz sınırını sayı olarak yazın (Örn: 50):")
    return CUSTOM_DEVICE

async def receive_custom_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['device_limit'] = int(update.message.text)
    return await finalize_key_creation(update, context)

# Adım 4: Key Oluşturma ve Kaydetme
async def device_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    dev_map = {"dev_100": 100, "dev_250": 250, "dev_500": 500, "dev_1000": 1000}
    context.user_data['device_limit'] = dev_map[query.data]
    
    return await finalize_key_creation(update, context)

async def finalize_key_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key_text = context.user_data['key_text']
    duration = context.user_data['duration']
    device_limit = context.user_data['device_limit']
    
    # DB Kayıt
    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO keys (key_text, duration, device_limit, is_frozen) VALUES (?, ?, ?, 0)",
                   (key_text, duration, device_limit))
    conn.commit()
    conn.close()
    
    text = (
        f"✅ **Key Başarıyla Oluşturuldu!**\n\n"
        f"🔑 **Key:** `{key_text}`\n"
        f"⏳ **Süre:** {duration}\n"
        f"📱 **Cihaz Sınırı:** {device_limit}\n"
        f"❄️ **Durum:** Aktif"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        
    return ConversationHandler.END

# Placeholder - Toggle Freeze
async def toggle_freeze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Key dondurma özelliği yakında aktif olacak.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]]))

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_key, pattern="^add_key$")],
        states={
            CHOOSING_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_key_text)],
            CUSTOM_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_duration)],
            CHOOSING_DEVICE: [
                CallbackQueryHandler(duration_selected, pattern="^dur_(1h|1d|7d|15d|30d)$"),
                CallbackQueryHandler(custom_duration_prompt, pattern="^dur_custom$"),
                CallbackQueryHandler(device_selected, pattern="^dev_(100|250|500|1000)$"),
                CallbackQueryHandler(custom_device_prompt, pattern="^dev_custom$")
            ],
            CUSTOM_DEVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_device)]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^main_menu$"))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
