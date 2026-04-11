import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ChatJoinRequest, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from flask import Flask

API_TOKEN = "8386393114:AAGZwzCy4b5PGbO79VeDMlLPhJcGgbXRxi4"
ADMIN_ID = 7467619605

CHANNEL_ID = -1003758162553
BOT_USERNAME = "Incloudrefbot"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ===== DB =====
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

# ===== КЛАВИАТУРЫ =====
def main_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Меню", callback_data="menu")
        ],
        [
            InlineKeyboardButton(text="📢 Канал", url="https://t.me/+qHEfLgFh-OpkZjc0")
        ],
        [
            InlineKeyboardButton(
                text="👥 Пригласить друзей",
                url=f"https://t.me/{BOT_USERNAME}?start={user_id}"
            )
        ]
    ])

def menu_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
            InlineKeyboardButton(text="🏆 Топ", callback_data="top")
        ],
        [
            InlineKeyboardButton(
                text="👥 Рефералка",
                url=f"https://t.me/{BOT_USERNAME}?start={user_id}"
            )
        ],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data="back")
        ]
    ])

# ===== START =====
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

# ===== MENU =====
@router.callback_query(F.data == "menu")
async def menu(call: CallbackQuery):
    await call.message.edit_text("📋 Меню:", reply_markup=menu_kb(call.from_user.id))

@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("👋 Главное меню", reply_markup=main_kb(call.from_user.id))

# ===== BALANCE =====
@router.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,))
    bal = cur.fetchone()[0]
    await call.message.answer(f"💰 Баланс: {bal}")

# ===== TOP =====
@router.callback_query(F.data == "top")
async def top(call: CallbackQuery):
    cur.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    users = cur.fetchall()

    text = "🏆 Топ:\n\n"
    for i, (uid, bal) in enumerate(users, 1):
        text += f"{i}. {uid} — {bal}\n"

    await call.message.answer(text)

# ===== BROADCAST =====
@router.message(Command("broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast ", "")

    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()

    for u in users:
        try:
            await bot.send_message(u[0], text)
        except:
            pass

    await message.answer("✅ Рассылка отправлена")

# ===== JOIN REQUEST AUTO =====
@router.chat_join_request()
async def join(req: ChatJoinRequest):
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

    cur.execute("UPDATE users SET is_subscribed=1 WHERE user_id=?", (user_id,))

    if ref_id:
        cur.execute("UPDATE users SET balance = balance + 1 WHERE user_id=?", (ref_id,))

    conn.commit()

    await req.approve()

# ===== FLASK ADMIN =====
app = Flask(__name__)

@app.route("/")
def index():
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]

    cur.execute("SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 5")
    top = cur.fetchall()

    html = f"<h1>Users: {total}</h1><h2>Top:</h2>"
    for u in top:
        html += f"<p>{u[0]} — {u[1]}</p>"
    return html

# ===== RUN =====
async def main():
    asyncio.create_task(dp.start_polling(bot))

    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
