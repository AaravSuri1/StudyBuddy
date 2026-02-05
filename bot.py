import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import telebot
from telebot import types
from openai import OpenAI
from datetime import date
import sqlite3
from PIL import Image

# ======================
# CONFIG
# ======================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ADMIN_ID = 123456789  # <-- PUT YOUR TELEGRAM USER ID

bot = telebot.TeleBot(BOT_TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

# ======================
# DATABASE
# ======================
conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER,
    day TEXT,
    count INTEGER,
    premium INTEGER
)
""")
conn.commit()

# ======================
# HELPERS
# ======================
def get_user(user_id):
    today = str(date.today())
    cur.execute("SELECT * FROM users WHERE user_id=? AND day=?", (user_id, today))
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            (user_id, today, 0, 0)
        )
        conn.commit()
        return 0, 0
    return row[2], row[3]

def increment_count(user_id):
    today = str(date.today())
    cur.execute(
        "UPDATE users SET count = count + 1 WHERE user_id=? AND day=?",
        (user_id, today)
    )
    conn.commit()

def set_premium(user_id):
    today = str(date.today())
    cur.execute(
        "UPDATE users SET premium=1 WHERE user_id=? AND day=?",
        (user_id, today)
    )
    conn.commit()

# ======================
# START
# ======================
@bot.message_handler(commands=['start'])
def start(message):
    text = (
        "👋 *Welcome to StepSolve AI* 🤖\n\n"
        "📚 Subjects: Maths, Science, English, SST\n"
        "🧠 Step-by-step + exam-ready answers\n\n"
        "🎁 Free: 3 questions/day\n"
        "💎 Premium: Unlimited\n\n"
        "✍️ Send question like:\n"
        "`Maths: Solve x² − 5x + 6 = 0`\n\n"
        "📸 Or send a photo of your question"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# ======================
# TEXT QUESTIONS
# ======================
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    count, premium = get_user(user_id)

    if count >= 3 and premium == 0:
        bot.reply_to(
            message,
            "❌ Daily limit reached.\n\n"
            "💎 Premium = Unlimited questions\n"
            "Pay via guardian UPI & send screenshot.\n\n"
            "Type /premium for details."
        )
        return

    increment_count(user_id)

    prompt = f"""
You are a strict but friendly school teacher.

Rules:
- Explain step by step
- Exam-oriented format
- Simple language (Class 6–10)
- Show formulas and logic
- End with final answer

Question:
{message.text}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700
    )

    bot.reply_to(message, response.choices[0].message.content)

# ======================
# PHOTO QUESTIONS
# ======================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    count, premium = get_user(user_id)

    if count >= 3 and premium == 0:
        bot.reply_to(message, "❌ Daily limit reached. Type /premium")
        return

    increment_count(user_id)

    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)

    with open("question.jpg", "wb") as f:
        f.write(downloaded)

    prompt = """
Solve the question shown in the image.
Explain step by step.
Use exam-oriented language.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    bot.reply_to(message, response.choices[0].message.content)

# ======================
# PREMIUM INFO
# ======================
@bot.message_handler(commands=['premium'])
def premium(message):
    bot.reply_to(
        message,
        "💎 *Premium Plan*\n\n"
        "✔ Unlimited questions\n"
        "✔ Exam-oriented answers\n"
        "✔ Photo questions\n\n"
        "💰 Price: ₹99/month\n"
        "👨‍👩‍👧 Guardian UPI only\n\n"
        "📸 Send payment screenshot here.",
        parse_mode="Markdown"
    )

# ======================
# ADMIN UNLOCK
# ======================
@bot.message_handler(commands=['unlock'])
def unlock(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        user_id = int(message.text.split()[1])
        set_premium(user_id)
        bot.send_message(user_id, "✅ Premium unlocked. Enjoy unlimited access 🎉")
        bot.reply_to(message, "User unlocked.")
    except:
        bot.reply_to(message, "Usage: /unlock USER_ID")

# ======================
# RUN
# ======================
print("🚀 StepSolve AI is running...")
bot.polling(non_stop=True)