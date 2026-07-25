import os
import sys
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import psycopg2

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ Ошибка: DATABASE_URL не найдена в переменных окружения.")
    sys.exit(1)

print("✅ DATABASE_URL загружена")

EKAT = timezone(timedelta(hours=5))
CREATOR_ID = 6573154279  # твой Telegram ID

VIP_PRICE = 500
PREMIUM_PRICE = 1000
GOLD_7_PRICE = 1500
GOLD_30_PRICE = 4000
GOLD_90_PRICE = 9000

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
        CREATE TABLE IF NOT EXISTS users (
            login TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 100,
            vip BOOLEAN DEFAULT FALSE,
            premium BOOLEAN DEFAULT FALSE,
            gold_until TIMESTAMP,
            last_daily TIMESTAMP,
            daily_count INTEGER DEFAULT 0,
            shop_count INTEGER DEFAULT 0,
            login_count INTEGER DEFAULT 0,
            game_count INTEGER DEFAULT 0,
            win_count INTEGER DEFAULT 0,
            add_count INTEGER DEFAULT 0,
            total_transfer INTEGER DEFAULT 0,
            max_spend INTEGER DEFAULT 0,
            max_win INTEGER DEFAULT 0,
            gold_days INTEGER DEFAULT 0,
            gold_90 BOOLEAN DEFAULT FALSE,
            restored BOOLEAN DEFAULT FALSE,
            profile_used BOOLEAN DEFAULT FALSE,
            achievements TEXT[] DEFAULT '{}',
            claimed_achievements TEXT[] DEFAULT '{}',
            telegram_id TEXT NOT NULL,
            admin_level INTEGER DEFAULT 0,
            banned BOOLEAN DEFAULT FALSE,
            ban_reason TEXT DEFAULT NULL
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Таблица users создана (или уже существует)")

init_db()

# === ДОСТИЖЕНИЯ ===
ACHIEVEMENTS = {
    "first_visit": {"name": "👋 Добро пожаловать!", "desc": "Зарегистрироваться", "reward": 10, "category": "activity"},
    "first_login": {"name": "🚪 Первый шаг", "desc": "Войти 1 раз", "reward": 10, "category": "activity"},
    "profile_first": {"name": "📋 Знакомство с ботом", "desc": "Написать /profile", "reward": 10, "category": "activity"},
    "login_7": {"name": "🏠 Постоянный гость", "desc": "Войти 7 раз", "reward": 25, "category": "activity"},
    "login_30": {"name": "🔒 Преданный игрок", "desc": "Войти 30 раз", "reward": 50, "category": "activity"},
    "first_daily": {"name": "🎁 Первый бонус", "desc": "Получить /daily 1 раз", "reward": 15, "category": "activity"},
    "daily_7": {"name": "🎯 Любитель бонусов", "desc": "Получить /daily 7 раз", "reward": 50, "category": "activity"},
    "daily_30": {"name": "💰 Бонус-маньяк", "desc": "Получить /daily 30 раз", "reward": 150, "category": "activity"},
    "daily_90": {"name": "📅 Ежедневный чемпион", "desc": "Получить /daily 90 раз", "reward": 300, "category": "activity"},
    "daily_365": {"name": "⭐ Легенда бонусов", "desc": "Получить /daily 365 раз", "reward": 1000, "category": "activity"},
    "rich_100": {"name": "💵 Сотня", "desc": "Иметь 100 монет", "reward": 20, "category": "wealth"},
    "rich_1000": {"name": "💳 Тысячник", "desc": "Иметь 1000 монет", "reward": 100, "category": "wealth"},
    "rich_5000": {"name": "🏦 Магнат", "desc": "Иметь 5000 монет", "reward": 300, "category": "wealth"},
    "rich_10000": {"name": "💎 Миллионер", "desc": "Иметь 10 000 монет", "reward": 500, "category": "wealth"},
    "rich_50000": {"name": "👑 Крез", "desc": "Иметь 50 000 монет", "reward": 1000, "category": "wealth"},
    "add_1": {"name": "📥 Накопитель", "desc": "Пополнить баланс 1 раз", "reward": 25, "category": "wealth"},
    "add_10": {"name": "📊 Инвестор", "desc": "Пополнить баланс 10 раз", "reward": 100, "category": "wealth"},
    "add_50": {"name": "💼 Спонсор", "desc": "Пополнить баланс 50 раз", "reward": 500, "category": "wealth"},
    "shop_3": {"name": "🛍️ Шопоголик", "desc": "3 покупки в магазине", "reward": 75, "category": "shop"},
    "shop_10": {"name": "🏪 Постоянный клиент", "desc": "10 покупок", "reward": 200, "category": "shop"},
    "shop_30": {"name": "🛒 Мега-покупатель", "desc": "30 покупок", "reward": 500, "category": "shop"},
    "buy_vip": {"name": "🟡 Владелец VIP", "desc": "Купить VIP", "reward": 50, "category": "shop"},
    "buy_premium": {"name": "🔷 Элита", "desc": "Купить Premium", "reward": 100, "category": "shop"},
    "buy_gold": {"name": "✨ Золотой", "desc": "Купить Gold", "reward": 200, "category": "shop"},
    "buy_gold_90": {"name": "🏅 Платина", "desc": "Купить Gold на 90 дней", "reward": 300, "category": "shop"},
    "game_1": {"name": "🎮 Первая игра", "desc": "Сыграть 1 раз", "reward": 20, "category": "games"},
    "game_10": {"name": "🕹️ Игроман", "desc": "Сыграть 10 раз", "reward": 100, "category": "games"},
    "game_50": {"name": "🎯 Профи", "desc": "Сыграть 50 раз", "reward": 300, "category": "games"},
    "game_100": {"name": "🧠 Мастер игры", "desc": "Сыграть 100 раз", "reward": 500, "category": "games"},
    "win_5": {"name": "🍀 Удачливый", "desc": "Выиграть 5 раз", "reward": 50, "category": "games"},
    "win_20": {"name": "🎲 Везунчик", "desc": "Выиграть 20 раз", "reward": 200, "category": "games"},
    "win_50": {"name": "🌈 Фортуна", "desc": "Выиграть 50 раз", "reward": 500, "category": "games"},
    "has_vip": {"name": "👑 VIP-владелец", "desc": "Иметь VIP статус", "reward": 50, "category": "special"},
    "has_premium": {"name": "💎 Premium-владелец", "desc": "Иметь Premium статус", "reward": 100, "category": "special"},
    "has_gold": {"name": "💛 Золотой подписчик", "desc": "Иметь активный Gold", "reward": 200, "category": "special"},
    "all_statuses": {"name": "🌟 Все статусы", "desc": "VIP+Premium+Gold", "reward": 1000, "category": "special"},
    "expert": {"name": "🏅 Эксперт", "desc": "Иметь 5 ачивок", "reward": 100, "category": "special"},
    "collector": {"name": "🗂️ Коллекционер", "desc": "Иметь 20 ачивок", "reward": 500, "category": "special"},
    "admin": {"name": "🔧 Админ", "desc": "Назначен администратором", "reward": 500, "category": "special"},
    "creator": {"name": "🧙 Создатель", "desc": "Создатель бота", "reward": 9999, "category": "special"},
}

CATEGORIES = {
    "activity": {"emoji": "🎯", "name": "Активность"},
    "wealth": {"emoji": "💰", "name": "Богатство"},
    "shop": {"emoji": "🛒", "name": "Магазин"},
    "games": {"emoji": "🎮", "name": "Игры"},
    "special": {"emoji": "🌟", "name": "Особые"},
}

# === РАБОТА С БД ===
def get_user(login):
    conn = get_db_connection()
    if not conn:
        return None
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE login = %s", (login,))
    row = cur.fetchone()
    if row:
        columns = [desc[0] for desc in cur.description]
        user = dict(zip(columns, row))
    else:
        user = None
    cur.close()
    conn.close()
    return user

def create_user(login, password, telegram_id):
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (login, password, telegram_id, balance, achievements, claimed_achievements, admin_level) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (login, password, telegram_id, 100, [], [], 0)
    )
    conn.commit()
    cur.close()
    conn.close()

def update_user(login, data):
    conn = get_db_connection()
    if not conn:
        return
    cur = conn.cursor()
    set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
    values = list(data.values()) + [login]
    cur.execute(f"UPDATE users SET {set_clause} WHERE login = %s", values)
    conn.commit()
    cur.close()
    conn.close()

def get_all_users():
    conn = get_db_connection()
    if not conn:
        return []
    cur = conn.cursor()
    cur.execute("SELECT login, balance FROM users ORDER BY balance DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# === СИСТЕМА АДМИНИСТРАТОРОВ И БАНА ===
def get_admin_level(login):
    user = get_user(login)
    if not user:
        return 0
    return user.get("admin_level", 0)

def is_admin(login, min_level=1):
    return get_admin_level(login) >= min_level

def is_banned(login):
    user = get_user(login)
    if not user:
        return False
    return user.get("banned", False)

def ban_user(login, reason=None):
    update_user(login, {"banned": True, "ban_reason": reason})

def unban_user(login):
    update_user(login, {"banned": False, "ban_reason": None})

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_status_icon(login):
    user = get_user(login)
    if not user or is_banned(login):
        return "🚫"
    if is_gold(login):
        return "💛"
    elif user.get("premium"):
        return "💎"
    elif user.get("vip"):
        return "👑"
    else:
        return "🟢"

def get_status_emoji(login):
    user = get_user(login)
    if not user:
        return "🟢 Обычный"
    if is_banned(login):
        return "🚫 Забанен"
    if is_gold(login):
        return "💛 Gold (подписка)"
    elif user.get("premium"):
        return "💎 Premium"
    elif user.get("vip"):
        return "👑 VIP"
    else:
        return "🟢 Обычный"

def is_gold(login):
    user = get_user(login)
    if not user or not user.get("gold_until"):
        return False
    try:
        until = user["gold_until"]
        if isinstance(until, str):
            until = datetime.strptime(until, "%Y-%m-%d %H:%M:%S")
        return datetime.now(EKAT) < until.replace(tzinfo=EKAT)
    except:
        return False

def check_achievement_condition(login, ach_id):
    user = get_user(login)
    if not user or is_banned(login):
        return False
    # Проверки для всех достижений
    if ach_id == "first_visit":
        return True
    elif ach_id == "first_login":
        return user.get("login_count", 0) >= 1
    elif ach_id == "profile_first":
        return user.get("profile_used", False)
    elif ach_id == "login_7":
        return user.get("login_count", 0) >= 7
    elif ach_id == "login_30":
        return user.get("login_count", 0) >= 30
    elif ach_id == "first_daily":
        return user.get("daily_count", 0) >= 1
    elif ach_id == "daily_7":
        return user.get("daily_count", 0) >= 7
    elif ach_id == "daily_30":
        return user.get("daily_count", 0) >= 30
    elif ach_id == "daily_90":
        return user.get("daily_count", 0) >= 90
    elif ach_id == "daily_365":
        return user.get("daily_count", 0) >= 365
    elif ach_id == "rich_100":
        return user["balance"] >= 100
    elif ach_id == "rich_1000":
        return user["balance"] >= 1000
    elif ach_id == "rich_5000":
        return user["balance"] >= 5000
    elif ach_id == "rich_10000":
        return user["balance"] >= 10000
    elif ach_id == "rich_50000":
        return user["balance"] >= 50000
    elif ach_id == "add_1":
        return user.get("add_count", 0) >= 1
    elif ach_id == "add_10":
        return user.get("add_count", 0) >= 10
    elif ach_id == "add_50":
        return user.get("add_count", 0) >= 50
    elif ach_id == "shop_3":
        return user.get("shop_count", 0) >= 3
    elif ach_id == "shop_10":
        return user.get("shop_count", 0) >= 10
    elif ach_id == "shop_30":
        return user.get("shop_count", 0) >= 30
    elif ach_id == "buy_vip":
        return user.get("vip", False)
    elif ach_id == "buy_premium":
        return user.get("premium", False)
    elif ach_id == "buy_gold":
        return is_gold(login)
    elif ach_id == "buy_gold_90":
        return is_gold(login) and user.get("gold_90", False)
    elif ach_id == "game_1":
        return user.get("game_count", 0) >= 1
    elif ach_id == "game_10":
        return user.get("game_count", 0) >= 10
    elif ach_id == "game_50":
        return user.get("game_count", 0) >= 50
    elif ach_id == "game_100":
        return user.get("game_count", 0) >= 100
    elif ach_id == "win_5":
        return user.get("win_count", 0) >= 5
    elif ach_id == "win_20":
        return user.get("win_count", 0) >= 20
    elif ach_id == "win_50":
        return user.get("win_count", 0) >= 50
    elif ach_id == "has_vip":
        return user.get("vip", False)
    elif ach_id == "has_premium":
        return user.get("premium", False)
    elif ach_id == "has_gold":
        return is_gold(login)
    elif ach_id == "all_statuses":
        return user.get("vip") and user.get("premium") and is_gold(login)
    elif ach_id == "expert":
        return len(user.get("achievements", [])) >= 5
    elif ach_id == "collector":
        return len(user.get("achievements", [])) >= 20
    elif ach_id == "admin":
        return int(user["telegram_id"]) == CREATOR_ID
    elif ach_id == "creator":
        return int(user["telegram_id"]) == CREATOR_ID
    return False

def get_achievement_progress(login, ach_id):
    user = get_user(login)
    if not user:
        return ""
    if ach_id == "login_7":
        return f"{user.get('login_count', 0)}/7"
    elif ach_id == "login_30":
        return f"{user.get('login_count', 0)}/30"
    elif ach_id == "daily_7":
        return f"{user.get('daily_count', 0)}/7"
    elif ach_id == "daily_30":
        return f"{user.get('daily_count', 0)}/30"
    elif ach_id == "daily_90":
        return f"{user.get('daily_count', 0)}/90"
    elif ach_id == "daily_365":
        return f"{user.get('daily_count', 0)}/365"
    elif ach_id == "rich_100":
        return f"{user['balance']}/100"
    elif ach_id == "rich_1000":
        return f"{user['balance']}/1000"
    elif ach_id == "rich_5000":
        return f"{user['balance']}/5000"
    elif ach_id == "rich_10000":
        return f"{user['balance']}/10000"
    elif ach_id == "rich_50000":
        return f"{user['balance']}/50000"
    elif ach_id == "add_1":
        return f"{user.get('add_count', 0)}/1"
    elif ach_id == "add_10":
        return f"{user.get('add_count', 0)}/10"
    elif ach_id == "add_50":
        return f"{user.get('add_count', 0)}/50"
    elif ach_id == "shop_3":
        return f"{user.get('shop_count', 0)}/3"
    elif ach_id == "shop_10":
        return f"{user.get('shop_count', 0)}/10"
    elif ach_id == "shop_30":
        return f"{user.get('shop_count', 0)}/30"
    elif ach_id == "game_1":
        return f"{user.get('game_count', 0)}/1"
    elif ach_id == "game_10":
        return f"{user.get('game_count', 0)}/10"
    elif ach_id == "game_50":
        return f"{user.get('game_count', 0)}/50"
    elif ach_id == "game_100":
        return f"{user.get('game_count', 0)}/100"
    elif ach_id == "win_5":
        return f"{user.get('win_count', 0)}/5"
    elif ach_id == "win_20":
        return f"{user.get('win_count', 0)}/20"
    elif ach_id == "win_50":
        return f"{user.get('win_count', 0)}/50"
    elif ach_id == "expert":
        return f"{len(user.get('achievements', []))}/5"
    elif ach_id == "collector":
        return f"{len(user.get('achievements', []))}/20"
    return ""

def check_and_unlock_achievements(login):
    user = get_user(login)
    if not user or is_banned(login):
        return []
    unlocked = user.get("achievements", [])
    new_achievements = []
    for ach_id in ACHIEVEMENTS:
        if ach_id not in unlocked and check_achievement_condition(login, ach_id):
            unlocked.append(ach_id)
            new_achievements.append(ach_id)
            reward = ACHIEVEMENTS[ach_id]["reward"]
            update_user(login, {"balance": user["balance"] + reward, "achievements": unlocked})
            user = get_user(login)
    return new_achievements

async def notify_achievements(update: Update, login, new_achievements):
    if not new_achievements:
        return
    text = "🏆 **Новые достижения!**\n\n"
    for ach_id in new_achievements:
        ach = ACHIEVEMENTS[ach_id]
        text += f"{ach['name']} — {ach['desc']} (+{ach['reward']} монет)\n"
    user = get_user(login)
    text += f"\nТекущий баланс: {user['balance']} монет"
    await update.message.reply_text(text, parse_mode="Markdown")

# === ОСНОВНЫЕ КОМАНДЫ ===
async def start(update: Update, context):
    login = context.user_data.get("login")
    if login:
        user = get_user(login)
        if user:
            if is_banned(login):
                await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
                return
            await update.message.reply_text(
                f"👋 С возвращением, {login}!\n\n"
                f"👤 Профиль:\n"
                f"Логин: {login}\n"
                f"Баланс: {user['balance']} монет\n"
                f"Статус: {get_status_emoji(login)}\n"
                f"Telegram ID: {user['telegram_id']}\n\n"
                "Доступные команды:\n"
                "/profile — показать профиль\n"
                "/daily — ежедневный бонус\n"
                "/shop — магазин статусов\n"
                "/gold — информация о Gold\n"
                "/achievements — список достижений\n"
                "/top — топ-10 по балансу\n"
                "/commands — список команд\n"
                "/changelog — история обновлений\n"
                "/logout — выйти"
            )
        else:
            await update.message.reply_text("❌ Ошибка загрузки профиля.")
    else:
        await update.message.reply_text(
            "Добро пожаловать! 🎉\n\n"
            "Чтобы продолжить, вам нужно зарегистрироваться.\n"
            "Придумайте логин и пароль и введите:\n"
            "/reg логин пароль\n\n"
            "Если у вас уже есть аккаунт, войдите:\n"
            "/login логин пароль\n\n"
            "Доступные команды:\n"
            "/profile — мой профиль\n"
            "/daily — ежедневный бонус\n"
            "/shop — магазин статусов\n"
            "/gold — информация о Gold\n"
            "/achievements — список достижений\n"
            "/top — топ-10 по балансу\n"
            "/commands — список команд\n"
            "/changelog — история обновлений\n"
            "/logout — выйти"
        )

async def register(update: Update, context):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используй: /reg логин пароль")
        return
    login, password = args[0], args[1]
    if get_user(login):
        await update.message.reply_text("❌ Логин уже занят.")
        return
    telegram_id = str(update.effective_user.id)
    create_user(login, password, telegram_id)
    if str(update.effective_user.id) == str(CREATOR_ID):
        update_user(login, {"admin_level": 3})
        await update.message.reply_text("👑 Вы назначены главным администратором.")
    await update.message.reply_text(f"✅ Регистрация успешна! Баланс: 100 монет.\nТеперь войди: /login {login} {password}")
    new_ach = check_and_unlock_achievements(login)
    if new_ach:
        await notify_achievements(update, login, new_ach)

async def login(update: Update, context):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Используй: /login логин пароль")
        return
    login, password = args[0], args[1]
    user = get_user(login)
    if not user:
        await update.message.reply_text("❌ Логин не найден.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if user["password"] != password:
        await update.message.reply_text("❌ Неверный пароль.")
        return
    context.user_data["login"] = login
    if str(update.effective_user.id) == str(CREATOR_ID):
        if user.get("admin_level", 0) < 3:
            update_user(login, {"admin_level": 3})
            await update.message.reply_text("👑 Ваш уровень повышен до главного администратора.")
            user = get_user(login)
    update_user(login, {"login_count": user.get("login_count", 0) + 1})
    user = get_user(login)
    status = get_status_emoji(login)
    if is_gold(login):
        status += f"\n⏳ Действует до: {user['gold_until']}"
    await update.message.reply_text(
        f"✅ Вход выполнен. Привет, {login}!\n\n"
        f"👤 Профиль:\n"
        f"Логин: {login}\n"
        f"Баланс: {user['balance']} монет\n"
        f"Статус: {status}\n"
        f"Telegram ID: {user['telegram_id']}"
    )
    new_ach = check_and_unlock_achievements(login)
    if new_ach:
        await notify_achievements(update, login, new_ach)

async def logout(update: Update, context):
    if "login" in context.user_data:
        del context.user_data["login"]
        await update.message.reply_text("✅ Вы вышли.")
    else:
        await update.message.reply_text("❌ Вы не авторизованы.")

async def profile(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите: /login логин пароль")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    user = get_user(login)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    update_user(login, {"profile_used": True})
    user = get_user(login)
    status = get_status_emoji(login)
    if is_gold(login):
        status += f"\n⏳ Действует до: {user['gold_until']}"
    await update.message.reply_text(
        f"👤 Профиль:\n"
        f"Логин: {login}\n"
        f"Баланс: {user['balance']} монет\n"
        f"Статус: {status}\n"
        f"Достижений: {len(user.get('achievements', []))}\n"
        f"Telegram ID: {user['telegram_id']}"
    )
    new_ach = check_and_unlock_achievements(login)
    if new_ach:
        await notify_achievements(update, login, new_ach)

async def daily(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    user = get_user(login)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    now = datetime.now(EKAT)
    last = user.get("last_daily")
    if last:
        if isinstance(last, str):
            last = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
        diff = now - last.replace(tzinfo=EKAT)
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await update.message.reply_text(
                f"⏳ Бонус уже получен. Следующий через {hours} ч {minutes} мин."
            )
            return
    bonus = 10
    if is_gold(login):
        bonus = 100
    elif user.get("premium"):
        bonus = 50
    elif user.get("vip"):
        bonus = 25
    update_user(login, {
        "balance": user["balance"] + bonus,
        "last_daily": now.strftime("%Y-%m-%d %H:%M:%S"),
        "daily_count": user.get("daily_count", 0) + 1
    })
    await update.message.reply_text(f"🎁 Ежедневный бонус: +{bonus} монет! Текущий баланс: {user['balance'] + bonus}")
    new_ach = check_and_unlock_achievements(login)
    if new_ach:
        await notify_achievements(update, login, new_ach)

async def gold_info(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    user = get_user(login)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    if is_gold(login):
        await update.message.reply_text(
            f"💛 У вас активна подписка GOLD!\n"
            f"Действует до: {user['gold_until']}\n\n"
            f"Бонусы:\n"
            f"✅ Ежедневный бонус — 100 монет\n"
            f"✅ Безлимитный баланс\n"
            f"✅ Безлимитные переводы\n"
            f"✅ Скидка 25% в магазине\n"
            f"✅ Кэшбэк 15%\n"
            f"✅ Эксклюзивные игры (скоро)\n"
            f"✅ Приоритетная поддержка"
        )
    else:
        await update.message.reply_text(
            f"❌ У вас нет подписки GOLD.\n\n"
            f"💛 GOLD — это максимальный статус с бонусами:\n"
            f"• 100 монет в день\n"
            f"• Безлимитный баланс и переводы\n"
            f"• Скидка 25% и кэшбэк 15%\n"
            f"• Эксклюзивные игры\n\n"
            f"Купить в /shop"
        )

# === МАГАЗИН ===
async def shop(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    status = get_status_emoji(login)
    keyboard = [
        [InlineKeyboardButton(f"👑 VIP — {VIP_PRICE} монет", callback_data="buy_vip")],
        [InlineKeyboardButton(f"💎 Premium — {PREMIUM_PRICE} монет", callback_data="buy_premium")],
        [InlineKeyboardButton(f"💛 GOLD 7 дней — {GOLD_7_PRICE} монет", callback_data="buy_gold_7")],
        [InlineKeyboardButton(f"💛 GOLD 30 дней — {GOLD_30_PRICE} монет", callback_data="buy_gold_30")],
        [InlineKeyboardButton(f"💛 GOLD 90 дней — {GOLD_90_PRICE} монет", callback_data="buy_gold_90")],
        [InlineKeyboardButton("❌ Закрыть", callback_data="close_shop")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛒 Магазин статусов\n\n"
        f"Ваш статус: {status}\n\n"
        f"👑 VIP — {VIP_PRICE} монет\n"
        f"💎 Premium — {PREMIUM_PRICE} монет\n"
        f"💛 GOLD (7д) — {GOLD_7_PRICE} монет\n"
        f"💛 GOLD (30д) — {GOLD_30_PRICE} монет\n"
        f"💛 GOLD (90д) — {GOLD_90_PRICE} монет\n\n"
        "Выберите опцию:",
        reply_markup=reply_markup
    )

async def shop_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    login = context.user_data.get("login")
    if not login:
        await query.edit_message_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await query.edit_message_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    user = get_user(login)
    if not user:
        await query.edit_message_text("❌ Пользователь не найден.")
        return
    data = query.data
    if data == "close_shop":
        await query.edit_message_text("🛒 Магазин закрыт.")
        return
    update_user(login, {"shop_count": user.get("shop_count", 0) + 1})
    user = get_user(login)
    if data == "buy_vip":
        if user.get("vip"):
            await query.edit_message_text("❌ У вас уже есть VIP.")
            return
        if user["balance"] < VIP_PRICE:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {VIP_PRICE}, у вас {user['balance']}.")
            return
        update_user(login, {"balance": user["balance"] - VIP_PRICE, "vip": True})
        await query.edit_message_text(f"✅ Поздравляем! Вы купили 👑 VIP за {VIP_PRICE} монет.")
    elif data == "buy_premium":
        if user.get("premium"):
            await query.edit_message_text("❌ У вас уже есть Premium.")
            return
        if user["balance"] < PREMIUM_PRICE:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {PREMIUM_PRICE}, у вас {user['balance']}.")
            return
        update_user(login, {"balance": user["balance"] - PREMIUM_PRICE, "premium": True})
        await query.edit_message_text(f"✅ Поздравляем! Вы купили 💎 Premium за {PREMIUM_PRICE} монет.")
    elif data == "buy_gold_7":
        if is_gold(login):
            await query.edit_message_text("❌ У вас уже есть Gold.")
            return
        if user["balance"] < GOLD_7_PRICE:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {GOLD_7_PRICE}, у вас {user['balance']}.")
            return
        until = (datetime.now(EKAT) + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        update_user(login, {"balance": user["balance"] - GOLD_7_PRICE, "gold_until": until, "gold_days": 7})
        await query.edit_message_text(f"✅ Поздравляем! Вы купили 💛 Gold на 7 дней!")
    elif data == "buy_gold_30":
        if is_gold(login):
            await query.edit_message_text("❌ У вас уже есть Gold.")
            return
        if user["balance"] < GOLD_30_PRICE:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {GOLD_30_PRICE}, у вас {user['balance']}.")
            return
        until = (datetime.now(EKAT) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        update_user(login, {"balance": user["balance"] - GOLD_30_PRICE, "gold_until": until, "gold_days": 30})
        await query.edit_message_text(f"✅ Поздравляем! Вы купили 💛 Gold на 30 дней!")
    elif data == "buy_gold_90":
        if is_gold(login):
            await query.edit_message_text("❌ У вас уже есть Gold.")
            return
        if user["balance"] < GOLD_90_PRICE:
            await query.edit_message_text(f"❌ Недостаточно монет. Нужно {GOLD_90_PRICE}, у вас {user['balance']}.")
            return
        until = (datetime.now(EKAT) + timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
        update_user(login, {"balance": user["balance"] - GOLD_90_PRICE, "gold_until": until, "gold_days": 90, "gold_90": True})
        await query.edit_message_text(f"✅ Поздравляем! Вы купили 💛 Gold на 90 дней!")
    new_ach = check_and_unlock_achievements(login)
    if new_ach:
        await notify_achievements(update, login, new_ach)

# === МЕНЮ ДОСТИЖЕНИЙ ===
async def achievements_menu(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    keyboard = []
    for cat_id, cat in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(f"{cat['emoji']} {cat['name']}", callback_data=f"ach_cat_{cat_id}")])
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="ach_close")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🏆 Выберите категорию достижений:", reply_markup=reply_markup)

async def achievements_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    login = context.user_data.get("login")
    if not login:
        await query.edit_message_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await query.edit_message_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    user = get_user(login)
    if not user:
        await query.edit_message_text("❌ Пользователь не найден.")
        return
    data = query.data
    if data == "ach_close":
        await query.edit_message_text("🏆 Меню достижений закрыто.")
        return
    if data.startswith("ach_cat_"):
        cat_id = data.replace("ach_cat_", "")
        cat = CATEGORIES[cat_id]
        unlocked = user.get("achievements", [])
        cat_achievements = [ach_id for ach_id, ach in ACHIEVEMENTS.items() if ach["category"] == cat_id]
        keyboard = []
        for ach_id in cat_achievements:
            ach = ACHIEVEMENTS[ach_id]
            status = "✅" if ach_id in unlocked else "⏳"
            progress = get_achievement_progress(login, ach_id)
            label = f"{status} {ach['name']}" + (f" ({progress})" if progress else "")
            keyboard.append([InlineKeyboardButton(label, callback_data=f"ach_view_{ach_id}")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="ach_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        count = len([a for a in cat_achievements if a in unlocked])
        total = len(cat_achievements)
        await query.edit_message_text(
            f"{cat['emoji']} {cat['name']} ({count}/{total})\n\nВыберите достижение:",
            reply_markup=reply_markup
        )
        return
    if data.startswith("ach_view_"):
        ach_id = data.replace("ach_view_", "")
        ach = ACHIEVEMENTS[ach_id]
        unlocked = user.get("achievements", [])
        claimed = user.get("claimed_achievements", [])
        is_unlocked = ach_id in unlocked
        status_text = "✅ Выполнено" if is_unlocked else "⏳ Не выполнено"
        progress = get_achievement_progress(login, ach_id)
        desc = f"{ach['desc']} ({progress})" if progress else ach['desc']
        keyboard = []
        if is_unlocked and ach_id not in claimed:
            keyboard.append([InlineKeyboardButton("🎁 Забрать награду", callback_data=f"ach_claim_{ach_id}")])
        elif is_unlocked and ach_id in claimed:
            keyboard.append([InlineKeyboardButton("✅ Награда получена", callback_data="ach_nope")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=f"ach_cat_{ach['category']}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🏅 {ach['name']}\n\n"
            f"📝 Описание: {desc}\n"
            f"📊 Статус: {status_text}\n"
            f"💰 Награда: {ach['reward']} монет",
            reply_markup=reply_markup
        )
        return
    if data.startswith("ach_claim_"):
        ach_id = data.replace("ach_claim_", "")
        ach = ACHIEVEMENTS[ach_id]
        unlocked = user.get("achievements", [])
        claimed = user.get("claimed_achievements", [])
        if ach_id not in unlocked:
            await query.edit_message_text("❌ Достижение ещё не выполнено.")
            return
        if ach_id in claimed:
            await query.edit_message_text("✅ Вы уже получили награду за это достижение.")
            return
        update_user(login, {"balance": user["balance"] + ach["reward"], "claimed_achievements": claimed + [ach_id]})
        user = get_user(login)
        await query.edit_message_text(
            f"🎉 Поздравляем!\n\n"
            f"Вы получили награду за достижение:\n"
            f"🏅 {ach['name']}\n"
            f"💰 +{ach['reward']} монет\n"
            f"Текущий баланс: {user['balance']} монет"
        )
        return
    if data == "ach_back":
        await achievements_menu(update, context)

# === ТОП-10 ===
async def top(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    conn = get_db_connection()
    if not conn:
        await update.message.reply_text("❌ Ошибка подключения к базе данных.")
        return
    cur = conn.cursor()
    cur.execute("SELECT login, balance FROM users ORDER BY balance DESC LIMIT 10")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        await update.message.reply_text("📋 Пока нет пользователей.")
        return
    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 **ТОП-10 ПО БАЛАНСУ**\n\n"
    for i, (login, balance) in enumerate(rows, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        icon = get_status_icon(login)
        text += f"{medal} {login} {icon} — **{balance}** монет\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# === КОМАНДЫ /COMMANDS И /CHANGELOG ===
async def commands_list(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    text = (
        "📋 **ДОСТУПНЫЕ КОМАНДЫ**\n\n"
        "🤖 Бот версии: **v0.1**\n"
        "📅 Дата: **25 июля 2026 г.**\n\n"
        "🔹 **Основные:**\n"
        "/start — главное меню\n"
        "/profile — мой профиль\n"
        "/login — войти в аккаунт\n"
        "/reg — зарегистрироваться\n"
        "/logout — выйти\n\n"
        "🔹 **Экономика:**\n"
        "/daily — ежедневный бонус\n"
        "/shop — магазин статусов\n"
        "/gold — информация о Gold\n"
        "/top — топ-10 по балансу\n\n"
        "🔹 **Достижения:**\n"
        "/achievements — список достижений\n\n"
        "🔹 **Игры:**\n"
        "/game — играть (в разработке)\n\n"
        "🔹 **Информация:**\n"
        "/changelog — история обновлений\n"
        "/commands — этот список\n\n"
        "🔹 **Админ-команды (доступны только админам):**\n"
        "/admin — админ-панель\n"
        "/add сумма — пополнить баланс\n"
        "/give_vip @username — выдать VIP\n"
        "/give_premium @username — выдать Premium\n"
        "/ban @username причина — забанить\n"
        "/unban @username — разбанить\n"
        "/give_ach @username id — выдать достижение\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def changelog(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    text = (
        "📜 **ИСТОРИЯ ОБНОВЛЕНИЙ**\n\n"
        "🤖 Текущая версия: **v0.1**\n"
        "📅 Дата: **25 июля 2026 г.**\n\n"
        "🔹 **v0.1** (25.07.2026)\n"
        "  • Создан бот\n"
        "  • Добавлена регистрация и вход\n"
        "  • Добавлен баланс и профиль\n"
        "  • Добавлен ежедневный бонус\n"
        "  • Добавлен магазин статусов (VIP, Premium, Gold)\n"
        "  • Добавлена система достижений (50 штук)\n"
        "  • Добавлен топ-10 по балансу\n"
        "  • Добавлена админ-панель\n"
        "  • Добавлена система администраторов (3 уровня)\n"
        "  • Добавлена система бана с подтверждением\n"
        "  • Добавлена выдача достижений\n"
        "  • Добавлены команды /commands и /changelog\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# === АДМИН-ПАНЕЛЬ ===
async def admin_panel(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if get_admin_level(login) < 1:
        await update.message.reply_text("❌ Доступ запрещён. Вы не администратор.")
        return
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("📋 Список пользователей", callback_data="admin_list")],
        [InlineKeyboardButton("📋 Список админ-команд", callback_data="admin_commands")],
        [InlineKeyboardButton("👥 Список администраторов", callback_data="admin_list_admins")],
    ]
    if get_admin_level(login) == 3:
        keyboard.append([InlineKeyboardButton("❤‍🔥 Панель создателя", callback_data="admin_creator_panel")])
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔐 Админ-панель:", reply_markup=reply_markup)

async def admin_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    login = context.user_data.get("login")
    if not login:
        await query.edit_message_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await query.edit_message_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if get_admin_level(login) < 1:
        await query.edit_message_text("❌ Доступ запрещён.")
        return
    data = query.data

    if data == "admin_close":
        await query.edit_message_text("🔐 Админ-панель закрыта.")
        return

    if data == "admin_back_to_panel":
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("📋 Список пользователей", callback_data="admin_list")],
            [InlineKeyboardButton("📋 Список админ-команд", callback_data="admin_commands")],
            [InlineKeyboardButton("👥 Список администраторов", callback_data="admin_list_admins")],
        ]
        if get_admin_level(login) == 3:
            keyboard.append([InlineKeyboardButton("❤‍🔥 Панель создателя", callback_data="admin_creator_panel")])
        keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data="admin_close")])
        await query.edit_message_text("🔐 Админ-панель:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_creator_panel":
        if get_admin_level(login) != 3:
            await query.edit_message_text("❌ Только создатель.")
            return
        keyboard = [
            [InlineKeyboardButton("➕ Изменить баланс", callback_data="admin_change_balance")],
            [InlineKeyboardButton("🚫 Забанить пользователя", callback_data="admin_ban_user")],
            [InlineKeyboardButton("✅ Разбанить пользователя", callback_data="admin_unban_user")],
            [InlineKeyboardButton("➕ Назначить администратора", callback_data="admin_add_admin")],
            [InlineKeyboardButton("🏆 Выдать достижение", callback_data="admin_give_achievement")],
            [InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_panel")]
        ]
        await query.edit_message_text("❤‍🔥 Панель создателя:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_commands":
        text = (
            "📋 **АДМИН-КОМАНДЫ**\n\n"
            "🔹 /add сумма — пополнить баланс текущему аккаунту (ур. 3)\n"
            "🔹 /admin — открыть админ-панель (ур. 1+)\n"
            "🔹 /give_vip @username — выдать VIP статус (ур. 2+)\n"
            "🔹 /give_premium @username — выдать Premium статус (ур. 2+)\n"
            "🔹 /ban @username причина — забанить пользователя (ур. 3)\n"
            "🔹 /unban @username — разбанить пользователя (ур. 3)\n"
            "🔹 /give_ach @username id — выдать достижение (ур. 3)\n"
            "🔹 /stats_all — общая статистика по боту (ур. 1+)\n\n"
            "📌 Уровни админов:\n"
            "👑 Уровень 3 — Главный администратор (полный доступ)\n"
            "⚙️ Уровень 2 — Модератор\n"
            "🛠️ Уровень 1 — Помощник\n"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_panel")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_list_admins":
        rows = get_all_users()
        text = "👥 **АДМИНИСТРАТОРЫ**\n\n"
        found = False
        for login, _ in rows:
            level = get_admin_level(login)
            if level > 0:
                found = True
                emoji = "👑" if level == 3 else "⚙️" if level == 2 else "🛠️"
                name = "Главный администратор" if level == 3 else "Модератор" if level == 2 else "Помощник"
                text += f"{emoji} {login} — {name} (уровень {level})\n"
        if not found:
            text += "❌ Администраторы не назначены."
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_panel")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "admin_stats":
        rows = get_all_users()
        total = len(rows)
        total_balance = sum(u[1] for u in rows)
        await query.edit_message_text(f"📊 Статистика:\nПользователей: {total}\nОбщий баланс: {total_balance} монет")
        return

    if data == "admin_list":
        rows = get_all_users()[:10]
        if not rows:
            await query.edit_message_text("📋 Нет пользователей.")
            return
        text = "📋 Первые 10 пользователей:\n"
        for i, (login, balance) in enumerate(rows, 1):
            status = "🚫" if is_banned(login) else "✅"
            text += f"{i}. {login} {status} — {balance} монет\n"
        await query.edit_message_text(text)
        return

    if data == "admin_change_balance":
        await query.edit_message_text("Введи логин и новую сумму через пробел:\n`логин 500`\nПример: `alex 1500`", parse_mode="Markdown")
        context.user_data["admin_action"] = "change_balance"
        return

    if data == "admin_ban_user":
        await query.edit_message_text("Введи логин пользователя и причину через пробел:\n`alex Спам в чате`")
        context.user_data["admin_action"] = "ban_user"
        return

    if data == "admin_unban_user":
        await query.edit_message_text("Введи логин пользователя для разбана:\n`alex`")
        context.user_data["admin_action"] = "unban_user"
        return

    if data == "admin_give_achievement":
        await query.edit_message_text("Введи логин и ID достижения через пробел:\n`alex rich_1000`")
        context.user_data["admin_action"] = "give_achievement"
        return

    if data == "ban_confirm_yes":
        ban_data = context.user_data.get("ban_confirm")
        if not ban_data:
            await query.edit_message_text("❌ Ошибка. Попробуй заново.")
            return
        target = ban_data["target"]
        reason = ban_data["reason"]
        ban_user(target, reason)
        await query.edit_message_text(f"✅ @{target} забанен. Причина: {reason}")
        user = get_user(target)
        if user and user.get("telegram_id"):
            try:
                await context.bot.send_message(
                    chat_id=int(user["telegram_id"]),
                    text=f"❌ **Вас забанили.**\n\nПричина: {reason}\nОбратитесь к администратору.",
                    parse_mode="Markdown"
                )
            except:
                pass
        context.user_data["ban_confirm"] = None
        return

    if data == "ban_confirm_no":
        context.user_data["ban_confirm"] = None
        await query.edit_message_text("❌ Бан отменён.")
        return

    if data == "admin_add_admin":
        if get_admin_level(login) != 3:
            await query.edit_message_text("❌ Только создатель может назначать.")
            return
        await query.edit_message_text("Введи логин пользователя, которому хочешь назначить администратора:")
        context.user_data["admin_action"] = "add_admin_login"
        return

    if data.startswith("admin_set_level_"):
        level = int(data.split("_")[3])
        target_login = context.user_data.get("temp_admin_login")
        if not target_login:
            await query.edit_message_text("❌ Ошибка. Попробуй заново.")
            return
        update_user(target_login, {"admin_level": level})
        await query.edit_message_text(f"✅ {target_login} назначен администратором уровня {level}.")
        context.user_data["temp_admin_login"] = None
        return

    if data == "admin_cancel_add":
        context.user_data["temp_admin_login"] = None
        await query.edit_message_text("❌ Назначение отменено.")
        return

# === ОБРАБОТЧИК ТЕКСТА ДЛЯ АДМИНОВ ===
async def handle_admin_text(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        return
    action = context.user_data.get("admin_action")

    if action == "change_balance":
        if get_admin_level(login) < 3:
            await update.message.reply_text("❌ Недостаточно прав.")
            context.user_data["admin_action"] = None
            return
        try:
            target_login, amount_str = update.message.text.split()
            amount = int(amount_str)
            user = get_user(target_login)
            if not user:
                await update.message.reply_text("❌ Пользователь не найден.")
                return
            update_user(target_login, {"balance": amount})
            await update.message.reply_text(f"✅ Баланс {target_login} изменён на {amount} монет.")
        except ValueError:
            await update.message.reply_text("❌ Введи два значения: логин и число (например, `alex 500`)")
        except:
            await update.message.reply_text("❌ Ошибка. Используй формат: `логин 500`")
        context.user_data["admin_action"] = None
        return

    if action == "ban_user":
        if get_admin_level(login) < 3:
            await update.message.reply_text("❌ Недостаточно прав.")
            context.user_data["admin_action"] = None
            return
        parts = update.message.text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Используй формат: `alex Спам в чате`")
            context.user_data["admin_action"] = None
            return
        target = parts[0]
        reason = " ".join(parts[1:])
        user = get_user(target)
        if not user:
            await update.message.reply_text("❌ Пользователь не найден.")
            context.user_data["admin_action"] = None
            return
        if is_banned(target):
            await update.message.reply_text("❌ Пользователь уже забанен.")
            context.user_data["admin_action"] = None
            return
        context.user_data["ban_confirm"] = {"target": target, "reason": reason}
        keyboard = [
            [InlineKeyboardButton("✅ Да, забанить", callback_data="ban_confirm_yes")],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data="ban_confirm_no")]
        ]
        await update.message.reply_text(
            f"🚫 **ВЫ ТОЧНО ХОТИТЕ ЗАБАНИТЬ ИГРОКА?**\n\n"
            f"Логин: {target}\n"
            f"Причина: {reason}\n\n"
            f"Действие необратимо.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data["admin_action"] = None
        return

    if action == "unban_user":
        if get_admin_level(login) < 3:
            await update.message.reply_text("❌ Недостаточно прав.")
            context.user_data["admin_action"] = None
            return
        target = update.message.text.strip()
        user = get_user(target)
        if not user:
            await update.message.reply_text("❌ Пользователь не найден.")
            context.user_data["admin_action"] = None
            return
        if not is_banned(target):
            await update.message.reply_text("❌ Пользователь не забанен.")
            context.user_data["admin_action"] = None
            return
        unban_user(target)
        await update.message.reply_text(f"✅ @{target} разбанен.")
        context.user_data["admin_action"] = None
        return

    if action == "give_achievement":
        if get_admin_level(login) < 3:
            await update.message.reply_text("❌ Недостаточно прав.")
            context.user_data["admin_action"] = None
            return
        parts = update.message.text.split()
        if len(parts) < 2:
            await update.message.reply_text("❌ Используй формат: `alex rich_1000`")
            context.user_data["admin_action"] = None
            return
        target = parts[0]
        ach_id = parts[1]
        user = get_user(target)
        if not user:
            await update.message.reply_text("❌ Пользователь не найден.")
            context.user_data["admin_action"] = None
            return
        if ach_id not in ACHIEVEMENTS:
            await update.message.reply_text("❌ Неверный ID достижения.")
            context.user_data["admin_action"] = None
            return
        unlocked = user.get("achievements", [])
        if ach_id in unlocked:
            await update.message.reply_text("❌ У пользователя уже есть это достижение.")
            context.user_data["admin_action"] = None
            return
        unlocked.append(ach_id)
        reward = ACHIEVEMENTS[ach_id]["reward"]
        update_user(target, {"achievements": unlocked, "balance": user["balance"] + reward})
        await update.message.reply_text(f"✅ Достижение «{ACHIEVEMENTS[ach_id]['name']}» выдано @{target} (+{reward} монет).")
        if user.get("telegram_id"):
            try:
                await context.bot.send_message(
                    chat_id=int(user["telegram_id"]),
                    text=f"🏆 Вам выдано достижение:\n{ACHIEVEMENTS[ach_id]['name']}\nНаграда: +{reward} монет"
                )
            except:
                pass
        context.user_data["admin_action"] = None
        return

    if action == "add_admin_login":
        if get_admin_level(login) != 3:
            await update.message.reply_text("❌ Только создатель может назначать.")
            context.user_data["admin_action"] = None
            return
        target_login = update.message.text.strip()
        user = get_user(target_login)
        if not user:
            await update.message.reply_text("❌ Пользователь не найден.")
            context.user_data["admin_action"] = None
            return
        context.user_data["temp_admin_login"] = target_login
        keyboard = [
            [InlineKeyboardButton("👑 Главный администратор (уровень 3)", callback_data="admin_set_level_3")],
            [InlineKeyboardButton("⚙️ Модератор (уровень 2)", callback_data="admin_set_level_2")],
            [InlineKeyboardButton("🛠️ Помощник (уровень 1)", callback_data="admin_set_level_1")],
            [InlineKeyboardButton("❌ Отмена", callback_data="admin_cancel_add")]
        ]
        await update.message.reply_text(
            f"Выбери уровень для {target_login}:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["admin_action"] = None
        return

# === КОМАНДА /ADD ===
async def add_balance(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if get_admin_level(login) < 3:
        await update.message.reply_text("❌ Доступ запрещён. Только для создателя.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Укажи сумму: /add 50")
        return
    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Сумма должна быть числом")
        return
    user = get_user(login)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    update_user(login, {"balance": user["balance"] + amount, "add_count": user.get("add_count", 0) + 1})
    await update.message.reply_text(f"✅ Баланс пополнен на {amount}.")

# === ИГРА (ЗАГЛУШКА) ===
async def game(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    user = get_user(login)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    update_user(login, {"game_count": user.get("game_count", 0) + 1})
    await update.message.reply_text("🎮 Игра запущена! (заглушка)")

# === ВЫДАТЬ СТАТУС (админ-команды) ===
async def give_status(update: Update, context, status_type):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if get_admin_level(login) < 2:
        await update.message.reply_text("❌ Недостаточно прав. Требуется уровень 2+.")
        return
    if not context.args:
        await update.message.reply_text(f"Используй: /{status_type} @username")
        return
    target = context.args[0].lstrip("@")
    user = get_user(target)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return    update_user(target, {status_type: True})
    await update.message.reply_text(f"✅ {status_type.upper()} выдан @{target}.")

async def give_vip(update: Update, context):
    await give_status(update, context, "vip")

async def give_premium(update: Update, context):
    await give_status(update, context, "premium")

# === КОМАНДА БАНА (ЧЕРЕЗ ТЕКСТ) ===
async def ban(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if get_admin_level(login) < 3:
        await update.message.reply_text("❌ Недостаточно прав. Требуется уровень 3.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("Используй: /ban @username [причина]")
        return
    target = context.args[0].lstrip("@")
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причины"
    user = get_user(target)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    if is_banned(target):
        await update.message.reply_text("❌ Пользователь уже забанен.")
        return
    context.user_data["ban_confirm"] = {"target": target, "reason": reason}
    keyboard = [
        [InlineKeyboardButton("✅ Да, забанить", callback_data="ban_confirm_yes")],
        [InlineKeyboardButton("❌ Нет, отмена", callback_data="ban_confirm_no")]
    ]
    await update.message.reply_text(
        f"🚫 **ВЫ ТОЧНО ХОТИТЕ ЗАБАНИТЬ ИГРОКА?**\n\n"
        f"Логин: {target}\n"
        f"Причина: {reason}\n\n"
        f"Действие необратимо.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def unban(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if get_admin_level(login) < 3:
        await update.message.reply_text("❌ Недостаточно прав. Требуется уровень 3.")
        return
    if not context.args:
        await update.message.reply_text("Используй: /unban @username")
        return
    target = context.args[0].lstrip("@")
    user = get_user(target)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    if not is_banned(target):
        await update.message.reply_text("❌ Пользователь не забанен.")
        return
    unban_user(target)
    await update.message.reply_text(f"✅ @{target} разбанен.")

# === КОМАНДА ВЫДАЧИ ДОСТИЖЕНИЯ (ЧЕРЕЗ ТЕКСТ) ===
async def give_achievement(update: Update, context):
    login = context.user_data.get("login")
    if not login:
        await update.message.reply_text("❌ Сначала войдите.")
        return
    if is_banned(login):
        await update.message.reply_text("🚫 Вы забанены. Обратитесь к администратору.")
        return
    if get_admin_level(login) < 3:
        await update.message.reply_text("❌ Недостаточно прав. Требуется уровень 3.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /give_ach @username achievement_id")
        return
    target = context.args[0].lstrip("@")
    ach_id = context.args[1]
    user = get_user(target)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден.")
        return
    if ach_id not in ACHIEVEMENTS:
        await update.message.reply_text("❌ Неверный ID достижения.")
        return
    unlocked = user.get("achievements", [])
    if ach_id in unlocked:
        await update.message.reply_text("❌ У пользователя уже есть это достижение.")
        return
    unlocked.append(ach_id)
    reward = ACHIEVEMENTS[ach_id]["reward"]
    update_user(target, {"achievements": unlocked, "balance": user["balance"] + reward})
    await update.message.reply_text(f"✅ Достижение «{ACHIEVEMENTS[ach_id]['name']}» выдано @{target} (+{reward} монет).")
    if user.get("telegram_id"):
        try:
            await context.bot.send_message(
                chat_id=int(user["telegram_id"]),
                text=f"🏆 Вам выдано достижение:\n{ACHIEVEMENTS[ach_id]['name']}\nНаграда: +{reward} монет"
            )
        except:
            pass

# === ЭХО ===
async def echo(update: Update, context):
    if update.message.text:
        await update.message.reply_text(update.message.text)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reg", register))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("logout", logout))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("gold", gold_info))
    app.add_handler(CommandHandler("achievements", achievements_menu))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("commands", commands_list))
    app.add_handler(CommandHandler("changelog", changelog))
    app.add_handler(CommandHandler("add", add_balance))
    app.add_handler(CommandHandler("game", game))
    app.add_handler(CommandHandler("give_vip", give_vip))
    app.add_handler(CommandHandler("give_premium", give_premium))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("give_ach", give_achievement))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(shop_callback, pattern="^(buy_vip|buy_premium|buy_gold_7|buy_gold_30|buy_gold_90|close_shop)$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin_change_balance|admin_stats|admin_list|admin_close|admin_commands|admin_back_to_panel|admin_list_admins|admin_add_admin|admin_set_level_1|admin_set_level_2|admin_set_level_3|admin_cancel_add|admin_ban_user|admin_unban_user|ban_confirm_yes|ban_confirm_no|admin_creator_panel|admin_give_achievement)$"))
    app.add_handler(CallbackQueryHandler(achievements_callback, pattern="^(ach_|ach_cat_|ach_view_|ach_claim_|ach_back|ach_close)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text, block=False))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo, block=False))
    print("Бот полностью запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()