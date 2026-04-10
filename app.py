import os
import asyncio
import sqlite3
from threading import Thread

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ChatJoinRequest, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask, render_template_string

# ================= CONFIG =================

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))

CHANNEL_LINK = "https://t.me/+_TuDWhNkqRYyZjM0"
CHANNEL_USERNAME = "@Incloud Shop Tallinn"

if not API_TOKEN:
    raise ValueError("No API_TOKEN")

# ================= DB =================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    referrer_id INTEGER,
    balance INTEGER DEFAULT 0,
    is_subscribed INTEGER DEFAULT 0,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

def add_user(user_id, username, full_name, referrer_id=None):
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if cur.fetchone():
        return

    cur.execute("""
    INSERT INTO users (user_id, username, full_name, referrer_id)
    VALUES (?, ?, ?, ?)
    """, (user_id, username, full_name, referrer_id))

    conn.commit()

def get_users():
    cur.execute("SELECT * FROM users")
    return cur.fetchall()

def get_top():
    cur.execute("""
    SELECT username, balance FROM users
    ORDER BY balance DESC LIMIT 10
    """)
    return cur.fetchall()

# ================= BOT =================

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

# ===== КНОПКИ

kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Проверить подписку")],
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🏆 Топ")]
    ],
    resize_keyboard=True
)

# ===== ПРОВЕРКА ПОДПИСКИ

async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ===== START

@router.message(F.text.startswith("/start"))
async def start(message: Message):
    args = message.text.split()

    ref_id = None
    if len(args) > 1:
        try:
            ref_id = int(args[1])
        except:
            pass

    user = message.from_user

    add_user(
        user.id,
        user.username or "no_username",
        user.full_name,
        referrer_id=ref_id
    )

    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.id}"

    await message.answer(
        f"👋 Привет!\n\n"
        f"📢 Подпишись на канал:\n{CHANNEL_LINK}\n\n"
        f"🔗 Твоя реферальная ссылка:\n{ref_link}\n\n"
        f"После подписки нажми кнопку ниже 👇",
        reply_markup=kb
    )

# ===== ПРОВЕРКА

@router.message(F.text == "✅ Проверить подписку")
async def check_sub(message: Message):
    user_id = message.from_user.id

    is_sub = await check_subscription(user_id)

    if not is_sub:
        await message.answer("❌ Ты не подписан на канал")
        return

    cur.execute("SELECT is_subscribed, referrer_id FROM users WHERE user_id=?", (user_id,))
    data = cur.fetchone()

    if not data:
        return

    is_done, ref_id = data

    if is_done:
        await message.answer("✅ Уже засчитано")
        return

    # отмечаем подписку
    cur.execute("UPDATE users SET is_subscribed=1 WHERE user_id=?", (user_id,))

    # начисляем рефералу
    if ref_id:
        cur.execute("UPDATE users SET balance = balance + 1 WHERE user_id=?", (ref_id,))

    conn.commit()

    await message.answer("🎉 Подписка подтверждена!")

# ===== БАЛАНС

@router.message(F.text == "💰 Баланс")
async def balance(message: Message):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
    bal = cur.fetchone()

    await message.answer(f"💰 Твой баланс: {bal[0] if bal else 0}")

# ===== ТОП

@router.message(F.text == "🏆 Топ")
async def top(message: Message):
    data = get_top()

    text = "🏆 Топ рефералов:\n\n"
    for i, u in enumerate(data, 1):
        text += f"{i}. @{u[0]} — {u[1]}\n"

    await message.answer(text)

# ===== JOIN REQUEST (авто принятие)

@router.chat_join_request()
async def join(req: ChatJoinRequest):
    await req.approve()

# ===== BROADCAST

@router.message(F.text.startswith("/broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast", "").strip()
    users = get_users()

    for u in users:
        try:
            await bot.send_message(u[0], text)
            await asyncio.sleep(0.03)
        except:
            pass

    await message.answer("✅ Рассылка завершена")

# ================= WEB =================

app = Flask(__name__)

HTML = """
<h1>Admin Panel</h1>

<h2>Users: {{users|length}}</h2>

<h3>Top:</h3>
<ul>
{% for u in top %}
<li>{{u[0]}} — {{u[1]}}</li>
{% endfor %}
</ul>
"""

@app.route("/")
def index():
    return render_template_string(
        HTML,
        users=get_users(),
        top=get_top()
    )

def run_web():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ================= RUN =================

async def main():
    Thread(target=run_web, daemon=True).start()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
