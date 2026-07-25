import os
import sys
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import psycopg2

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ Ошибка: DATABASE_URL не найдена в переменных окружения.")
    sys.exit(1)

print("✅ DATABASE_URL загружена")

EKAT = timezone(timedelta(hours=5))

# === ПОДКЛЮЧЕНИЕ К БД ===
def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn:
        print("❌ Не удалось создать таблицу — нет подключения")
        return
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clicker_users (
            user_id TEXT PRIMARY KEY,
            login TEXT UNIQUE NOT NULL,
            balance INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            click_power INTEGER DEFAULT 1,
            auto_clicker_level INTEGER DEFAULT 0,
            multiplier_level INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            last_auto_click TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Таблица clicker_users создана (или уже существует)")

init_db()

# === РАБОТА С БД ===
def get_user(user_id):
    conn = get_db_connection()
    if not conn:
        return None
    cur = conn.cursor()
    cur.execute("SELECT * FROM clicker_users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {
            "user_id": row[0],
            "login": row[1],
            "balance": row[2],
            "clicks": row[3],
            "click_power": row[4],
            "auto_clicker_level": row[5],
            "multiplier_level": row[6],
            "total_earned": row[7],
            "last_auto_click": row[8]
        }
    return None

def create_user(user_id, login):
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO clicker_users (user_id, login) VALUES (%s, %s)",
        (user_id, login)
    )
    conn.commit()
    cur.close()
    conn.close()

def update_user(user_id, data):
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
    values = list(data.values()) + [user_id]
    cur.execute(f"UPDATE clicker_users SET {set_clause} WHERE user_id = %s", values)
    conn.commit()
    cur.close()
    conn.close()

# === ОСНОВНЫЕ КОМАНДЫ ===
async def start(update: Update, context):
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    if not user:
        await update.message.reply_text(
            "👋 Добро пожаловать в кликер-бот!\n\n"
            "Придумай логин и зарегистрируйся:\n"
            "/reg логин"
        )
        return
    keyboard = [
        [InlineKeyboardButton("👆 Кликнуть", callback_data="click")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("📈 Топ-10", callback_data="top")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Привет, {user['login']}!\n\n"
        f"💰 Баланс: {user['balance']} монет\n"
        f"🖱️ Кликов: {user['clicks']}\n"
        f"⚡ Сила клика: {user['click_power']}\n"
        f"🤖 Авто-кликер: уровень {user['auto_clicker_level']}\n"
        f"📈 Множитель: x{2 ** user['multiplier_level']}\n\n"
        "Выбери действие:",
        reply_markup=reply_markup
    )

async def register(update: Update, context):
    user_id = str(update.effective_user.id)
    if get_user(user_id):
        await update.message.reply_text("❌ Вы уже зарегистрированы.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Используй: /reg логин")
        return
    login = context.args[0]
    create_user(user_id, login)
    await update.message.reply_text(f"✅ Регистрация успешна! Добро пожаловать, {login}!")

async def click(update: Update, context):
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Сначала зарегистрируйся: /reg логин")
        return
    now = datetime.now(EKAT)
    last = user['last_auto_click']
    if last:
        if isinstance(last, str):
            last = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
        diff = (now - last.replace(tzinfo=EKAT)).seconds
        if diff >= 10 and user['auto_clicker_level'] > 0:
            # Начисляем авто-кликер
            auto_income = user['auto_clicker_level'] * (diff // 10)
            new_balance = user['balance'] + auto_income
            new_total = user['total_earned'] + auto_income
            update_user(user_id, {
                "balance": new_balance,
                "total_earned": new_total,
                "last_auto_click": now.strftime("%Y-%m-%d %H:%M:%S")
            })
            user = get_user(user_id)
    # Обычный клик
    power = user['click_power'] * (2 ** user['multiplier_level'])
    new_balance = user['balance'] + power
    new_clicks = user['clicks'] + 1
    new_total = user['total_earned'] + power
    update_user(user_id, {
        "balance": new_balance,
        "clicks": new_clicks,
        "total_earned": new_total
    })
    user = get_user(user_id)
    keyboard = [
        [InlineKeyboardButton("👆 Кликнуть", callback_data="click")],
        [InlineKeyboardButton("📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton("📈 Топ-10", callback_data="top")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            f"👋 Привет, {user['login']}!\n\n"
            f"💰 Баланс: {new_balance} монет (+{power})\n"
            f"🖱️ Кликов: {new_clicks}\n"
            f"⚡ Сила клика: {user['click_power']}\n"
            f"🤖 Авто-кликер: уровень {user['auto_clicker_level']}\n"
            f"📈 Множитель: x{2 ** user['multiplier_level']}\n\n"
            "Выбери действие:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"👆 Клик! +{power} монет. Баланс: {new_balance}",
            reply_markup=reply_markup
        )

async def profile(update: Update, context):
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Сначала зарегистрируйся: /reg логин")
        return
    text = (
        f"📊 **Профиль игрока**\n\n"
        f"👤 Логин: {user['login']}\n"
        f"💰 Баланс: {user['balance']} монет\n"
        f"🖱️ Всего кликов: {user['clicks']}\n"
        f"⚡ Сила клика: {user['click_power']}\n"
        f"🤖 Авто-кликер: уровень {user['auto_clicker_level']}\n"
        f"📈 Множитель: x{2 ** user['multiplier_level']}\n"
        f"💎 Всего заработано: {user['total_earned']} монет"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def shop(update: Update, context):
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Сначала зарегистрируйся.")
        return
    keyboard = [
        [InlineKeyboardButton("🤖 Авто-кликер (50 монет)", callback_data="buy_auto")],
        [InlineKeyboardButton("⚡ Увеличение силы клика (100 монет)", callback_data="buy_power")],
        [InlineKeyboardButton("📈 Множитель x2 (500 монет)", callback_data="buy_multiplier")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close_shop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛒 **Магазин улучшений**\n\n"
        f"💰 Твой баланс: {user['balance']} монет\n\n"
        f"🤖 Авто-кликер (уровень {user['auto_clicker_level']}) — 50 монет\n"
        f"   Приносит +1 монету каждые 10 секунд.\n\n"
        f"⚡ Сила клика (уровень {user['click_power']}) — 100 монет\n"
        f"   Увеличивает доход за клик на 1.\n\n"
        f"📈 Множитель x{2 ** user['multiplier_level']} (уровень {user['multiplier_level']}) — 500 монет\n"
        f"   Удваивает доход за клик.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def shop_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    user = get_user(user_id)
    if not user:
        await query.edit_message_text("❌ Сначала зарегистрируйся.")
        return
    data = query.data
    if data == "close_shop":
        await query.edit_message_text("🛒 Магазин закрыт.")
        return
    if data == "buy_auto":
        cost = 50
        if user['balance'] < cost:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {cost}.")
            return
        new_level = user['auto_clicker_level'] + 1
        update_user(user_id, {
            "balance": user['balance'] - cost,
            "auto_clicker_level": new_level
        })
        await query.edit_message_text(f"✅ Авто-кликер улучшен до уровня {new_level}!")
        return
    if data == "buy_power":
        cost = 100
        if user['balance'] < cost:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {cost}.")
            return
        new_power = user['click_power'] + 1
        update_user(user_id, {
            "balance": user['balance'] - cost,
            "click_power": new_power
        })
        await query.edit_message_text(f"✅ Сила клика увеличена до {new_power}!")
        return
    if data == "buy_multiplier":
        cost = 500
        if user['balance'] < cost:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {cost}.")
            return
        new_level = user['multiplier_level'] + 1
        update_user(user_id, {
            "balance": user['balance'] - cost,
            "multiplier_level": new_level
        })
        await query.edit_message_text(f"✅ Множитель улучшен до x{2 ** new_level}!")
        return

async def top(update: Update, context):
    conn = get_db_connection()
    if not conn:
        await update.message.reply_text("❌ Ошибка подключения к БД.")
        return
    cur = conn.cursor()
    cur.execute("SELECT login, balance FROM clicker_users ORDER BY balance DESC LIMIT 10")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        await update.message.reply_text("📋 Пока нет игроков.")
        return
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 **ТОП-10 ПО БАЛАНСУ**\n\n"
    for i, (login, balance) in enumerate(rows, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} {login} — **{balance}** монет\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# === CALLBACK ХЕНДЛЕР ===
async def callback_handler(update: Update, context):
    query = update.callback_query
    data = query.data
    if data == "click":
        await click(update, context)
    elif data == "profile":
        await profile(update, context)
    elif data == "shop":
        await shop(update, context)
    elif data == "top":
        await top(update, context)
    else:
        await shop_callback(update, context)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reg", register))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: u.message.reply_text("❌ Неизвестная команда. Используй /start")))
    print("Кликер-бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
