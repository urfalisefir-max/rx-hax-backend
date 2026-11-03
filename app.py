import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import sqlite3
from datetime import datetime, timedelta

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Yeni Key Botu Tokeni
KEY_BOT_TOKEN = "9009112136:AAFmLQrTB1u3InEw2vyX4sYGmdKPR_F_u1c"

# Veritabanı (keys.db) Kurulumu
def init_db():
    conn = sqlite3.connect("keys.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_text TEXT UNIQUE,
            duration TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔑 Key Yönetimi", callback_data="key_menu")],
        [InlineKeyboardButton("📊 Bot Durumu", callback_data="status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 Hoş geldin Yönetici! Ana panele hoş geldin.", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "key_menu":
        keyboard = [
            [InlineKeyboardButton("➕ Yeni Key Oluştur", callback_data="create_key")],
            [InlineKeyboardButton("🔙 Ana Menü", callback_data="main_menu")]
        ]
        await query.edit_message_text("🔑 **Key Yönetim Paneli**\n\nYapmak istediğin işlemi seç:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    elif query.data == "create_key":
        # Örnek Key Üretme Mantığı
        new_key = f"RX-{os.urandom(4).hex().upper()}-{os.urandom(4).hex().upper()}"
        conn = sqlite3.connect("keys.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO keys (key_text, duration, status) VALUES (?, ?, ?)", (new_key, "1 Gün", "Aktif"))
        conn.commit()
        conn.close()

        await query.edit_message_text(
            f"✅ **Key Başarıyla Oluşturuldu!**\n\n"
            f"🔑 `{new_key}`\n"
            f"⏱ Süre: 1 Gün\n"
            f"🟢 Durum: Aktif",
            parse_mode="Markdown"
        )

def main():
    app = ApplicationBuilder().token(KEY_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Key Botu Aktif!")
    app.run_polling()

if __name__ == "__main__":
    main()
        
