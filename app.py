import os
import asyncio
import sqlite3
from threading import Thread

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ChatJoinRequest

from flask import Flask, render_template_string

# =========================
# CONFIG
# =========================

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", 5000))

if not API_TOKEN:
    raise ValueError("API_TOKEN missing")

# =========================
# DB
# =========================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

def add_user(user_id, username, full_name):
    cur.execute("""
    INSERT OR IGNORE INTO users (user_id, username, full_name)
    VALUES (?, ?, ?)
    """, (user_id, username, full_name))
    conn.commit()

def get_users():
    cur.execute("SELECT * FROM users")
    return cur.fetchall()

def get_stats():
    cur.execute("""
    SELECT date(joined_at), COUNT(*)
    FROM users
    GROUP BY date(joined_at)
    ORDER BY date(joined_at)
    """)
    return cur.fetchall()

# =========================
# TELEGRAM BOT
# =========================

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

@router.message(F.text == "/start")
async def start(message: Message):
    await message.answer("🤖 Бот работает")

# JOIN REQUEST (подписка)
@router.chat_join_request()
async def join(req: ChatJoinRequest):
    u = req.from_user

    add_user(u.id, u.username or "no_username", u.full_name)
    await req.approve()

# ADMIN PANEL
@router.message(F.text == "/admin")
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    users = get_users()
    await message.answer(f"👑 Админ\nПользователей: {len(users)}")

# BROADCAST
@router.message(F.text.startswith("/broadcast"))
async def broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast", "").strip()

    users = get_users()

    sent = 0
    for u in users:
        try:
            await bot.send_message(u[0], text)
            sent += 1
            await asyncio.sleep(0.03)
        except:
            pass

    await message.answer(f"📢 Отправлено: {sent}")

async def run_bot():
    dp.include_router(router)
    await dp.start_polling(bot)

# =========================
# WEB (FLASK ADMIN PANEL)
# =========================

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Panel</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body style="font-family: Arial">

<h1>📊 Admin Panel</h1>

<h2>👥 Users: {{ users|length }}</h2>

<canvas id="chart" width="600" height="300"></canvas>

<script>
const ctx = document.getElementById('chart');

new Chart(ctx, {
    type: 'line',
    data: {
        labels: {{ labels|safe }},
        datasets: [{
            label: 'Users per day',
            data: {{ values|safe }},
            borderWidth: 2
        }]
    }
});
</script>

<h3>👤 Latest users</h3>

<ul>
{% for u in users[-20:] %}
<li>{{u[1]}} | {{u[2]}} | {{u[3]}}</li>
{% endfor %}
</ul>

</body>
</html>
"""

@app.route("/")
def index():
    users = get_users()
    stats = get_stats()

    labels = [x[0] for x in stats]
    values = [x[1] for x in stats]

    return render_template_string(
        HTML,
        users=users,
        labels=labels,
        values=values
    )

def run_web():
    app.run(host="0.0.0.0", port=PORT)

# =========================
# START BOTH
# =========================

async def main():
    Thread(target=run_web).start()
    await run_bot()

if __name__ == "__main__":
    asyncio.run(main())
