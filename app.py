import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from flask import Flask

API_TOKEN = "8386393114:AAGZwzCy4b5PGbO79VeDMlLPhJcGgbXRxi4"
ADMIN_ID = 7467619605

CHANNEL_ID = -1003758162553

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# БД
conn = sqlite3.connect("db.sqlite3")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    referrer_id INTEGER,
    balance INTEGER DEFAULT 0,
    is_subscribed INTEGER DEFAULT 0
)
""")
conn.commit()

# ===== КНОПКИ =====
def main_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Перейти в канал", url="https://t.me/+qHEfLgFh-OpkZjc0")],
        [InlineKeyboardButton(text="👥 Пригласить друзей", url=f"https://t.me/Incloudrefbot?start={user_id}"
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="🏆 Топ", callback_data="top")]
    ])

# ===== /start =====
@router.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id

    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 else None

    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, ref_id))
        conn.commit()

    await message.answer(
        "👋 Добро пожаловать!\n\nПодпишись на канал и приглашай друзей 🚀",
        reply_markup=main_kb(user_id)
    )

# ===== БАЛАНС =====
@router.callback_query(F.data == "balance")
async def balance(call):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,))
    bal = cur.fetchone()[0]

    await call.message.answer(f"💰 Твой баланс: {bal}")

# ===== ТОП =====
@router.callback_query(F.data == "top")
async def top(call):
    cur.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    users = cur.fetchall()

    text = "🏆 Топ рефералов:\n\n"
    for i, (uid, bal) in enumerate(users, 1):
        text += f"{i}. {uid} — {bal}\n"

    await call.message.answer(text)

# ===== РАССЫЛКА =====
@router.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast ", "")

    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()

    for user in users:
        try:
            await bot.send_message(user[0], text)
        except:
            pass

    await message.answer("✅ Рассылка завершена")

# ===== АВТОНАЧИСЛЕНИЕ =====
@router.chat_join_request()
async def join_request_handler(req: ChatJoinRequest):
    user_id = req.from_user.id

    cur.execute("SELECT is_subscribed, referrer_id FROM users WHERE user_id=?", (user_id,))
    data = cur.fetchone()

    if not data:
        await req.approve()
        return

    is_subscribed, ref_id = data

    if is_subscribed:
        await req.approve()
        return

    # отмечаем подписку
    cur.execute("UPDATE users SET is_subscribed=1 WHERE user_id=?", (user_id,))

    # начисляем рефереру
    if ref_id:
        cur.execute("UPDATE users SET balance = balance + 1 WHERE user_id=?", (ref_id,))

    conn.commit()

    await req.approve()

# ===== FLASK (веб админка) =====
app = Flask(__name__)

@app.route("/")
def index():
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]

    cur.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5")
    top_users = cur.fetchall()

    html = f"<h1>Users: {total}</h1><h2>Top:</h2>"
    for u in top_users:
        html += f"<p>{u[0]} — {u[1]}</p>"

    return html

# ===== ЗАПУСК =====
async def main():
    asyncio.create_task(dp.start_polling(bot))

    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
