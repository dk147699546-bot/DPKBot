import os
import sqlite3
import subprocess
from threading import Thread
from flask import Flask
import telebot

# --- FLASK KEEP-ALIVE SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "DPKHostBot Server is Running Live!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- CONFIGURATION ---
BOT_TOKEN = "8976542965:AAEaOjnmUgu6ulYIXkPYLimNjcIhGcPhef4"
ADMIN_ID = 8887398617
UPI_ID = "deepak-91k@fam"
PLAN_PRICE = 19
CONTACT_HANDLE = "@DeepakTechM"

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE SETUP ---
DATABASE_PATH = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, is_subscribed INTEGER DEFAULT 0, max_bots INTEGER DEFAULT 1)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_files 
                 (user_id INTEGER, file_name TEXT, file_type TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Active running processes storage
running_processes = {}
user_files = {}

def get_user_folder(user_id):
    folder = f"user_{user_id}"
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder

def is_user_subscribed(user_id):
    if user_id == ADMIN_ID:
        return True
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

def get_max_bots(user_id):
    if user_id == ADMIN_ID:
        return 999
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT max_bots FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 1

def run_script(file_path, user_id, user_folder, file_name):
    try:
        if user_id in running_processes and file_name in running_processes[user_id]:
            running_processes[user_id][file_name].terminate()

        proc = subprocess.Popen(["python", file_path], cwd=user_folder)
        if user_id not in running_processes:
            running_processes[user_id] = {}
        running_processes[user_id][file_name] = proc
        bot.send_message(user_id, f"🚀 Executing `{file_name}` in background...", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(user_id, f"❌ Failed to run `{file_name}`: {e}")

# --- BOT COMMAND HANDLERS ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    welcome_text = (
        f"👋 Welcome to DPK Host Bot!\n\n"
        f"🤖 Free Plan: Host 1 bot file (Max 10MB)\n"
        f"💎 Premium Plan (₹{PLAN_PRICE}/month): Host up to 15 bots!\n\n"
        f"Commands:\n"
        f"/plan - Check Subscription Status\n"
        f"/pay - Subscribe / Upgrade\n"
        f"/mybots - List active running bots\n"
        f"Contact Admin: {CONTACT_HANDLE}"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['plan'])
def check_plan(message):
    user_id = message.from_user.id
    subbed = is_user_subscribed(user_id)
    max_b = get_max_bots(user_id)
    status = "Active Subscriber 💎" if subbed else "Free User 🆓"
    bot.reply_to(message, f"📊 Your Status: {status}\nMax Bots Allowed: {max_b}")

@bot.message_handler(commands=['pay'])
def payment_info(message):
    pay_text = (
        f"💳 *Subscription Payment*\n\n"
        f"Price: ₹{PLAN_PRICE} / Month\n"
        f"UPI ID: `{UPI_ID}`\n\n"
        f"Payment karne ke baad UTR/Transaction ID is tarah bhejein:\n"
        f"`/verify <12-digit-UTR-Number>`"
    )
    bot.reply_to(message, pay_text, parse_mode="Markdown")

@bot.message_handler(commands=['verify'])
def verify_utr(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Direct format: `/verify 123456789012`", parse_mode="Markdown")
        return
    
    utr = args[1]
    bot.reply_to(message, f"⏳ UTR `{utr}` sent to Admin for verification. Please wait!", parse_mode="Markdown")
    
    admin_msg = (
        f"🔔 *New Payment Request*\n\n"
        f"User ID: `{user_id}`\n"
        f"UTR: `{utr}`\n\n"
        f"Approve karne ke liye command bhejein:\n"
        f"`/approve {user_id}`"
    )
    bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")

@bot.message_handler(commands=['approve'])
def approve_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Usage: `/approve <user_id>`")
        return
    
    target_id = int(args[1])
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET is_subscribed = 1, max_bots = 15 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()

    bot.reply_to(message, f"✅ Approved User `{target_id}` successfully!")
    bot.send_message(target_id, "🎉 Your subscription is active now! You can host up to 15 bots.")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    file_name = message.document.file_name
    file_size = message.document.file_size

    if file_size > 10 * 1024 * 1024:
        bot.reply_to(message, "❌ File size exceeds 10MB limit.")
        return

    max_b = get_max_bots(user_id)
    user_folder = get_user_folder(user_id)
    
    existing_files = [f for f in os.listdir(user_folder) if os.path.isfile(os.path.join(user_folder, f))]
    if file_name not in existing_files and len(existing_files) >= max_b:
        bot.reply_to(message, f"❌ Plan limit reached! Max bots allowed: {max_b}. Upgrade with /pay.")
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    file_path = os.path.join(user_folder, file_name)
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    bot.reply_to(message, f"✅ Saved `{file_name}` successfully!", parse_mode="Markdown")

    if file_name.endswith('.py'):
        run_script(file_path, user_id, user_folder, file_name)

if __name__ == '__main__':
    keep_alive()
    print("Bot starting...")
    bot.infinity_polling()
  
