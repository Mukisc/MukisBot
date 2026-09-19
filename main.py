import os
import sqlite3
import logging
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery
)

# --- Настройки окружения Render ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Ваш цифровой Telegram ID для админки

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения Render!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- База данных (SQLite) ---
DB_NAME = "gamestore.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Пользователи
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                joined_at TEXT
            )
        """)
        # Каталог игр
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                title TEXT,
                category TEXT,
                price_stars INTEGER,
                description TEXT
            )
        """)
        # Пул одноразовых ключей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keys_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                game_key TEXT UNIQUE,
                is_sold INTEGER DEFAULT 0
            )
        """)
        # История заказов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game_id TEXT,
                game_key TEXT,
                price_paid INTEGER,
                created_at TEXT
            )
        """)
        conn.commit()
        seed_data(conn)

def seed_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM games")
    if cursor.fetchone()[0] == 0:
        games = [
            ("cp2077", "Cyberpunk 2077: Phantom Liberty", "RPG", 150, "Мрачный Найт-Сити и масштабное дополнение."),
            ("er", "Elden Ring: Shadow of the Erdtree", "Action-RPG", 200, "Шедевр FromSoftware в Междуземье."),
            ("bg3", "Baldur's Gate 3", "RPG", 180, "Лучшая ролевая игра года по вселенной D&D."),
            ("gta5", "Grand Theft Auto V", "Action", 80, "Культовый экшен в Лос-Сантосе.")
        ]
        cursor.executemany("INSERT INTO games VALUES (?, ?, ?, ?, ?)", games)

        # Тестовые ключи в наличии
        keys = [
            ("cp2077", "CP77-AAAA-1111"), ("cp2077", "CP77-BBBB-2222"),
            ("er", "ELDEN-XXXX-9999"),
            ("bg3", "BG3-DOOR-8888"),
            ("gta5", "GTA5-ROCK-7777")
        ]
        cursor.executemany("INSERT OR IGNORE INTO keys_pool (game_id, game_key) VALUES (?, ?)", keys)
        conn.commit()

init_db()

# --- Вспомогательные функции БД ---
def get_user_orders(user_id: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT o.created_at, g.title, o.game_key, o.price_paid 
            FROM orders o 
            JOIN games g ON o.game_id = g.game_id 
            WHERE o.user_id = ? 
            ORDER BY o.order_id DESC
        """, (user_id,))
        return cursor.fetchall()

def get_available_key(game_id: str):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, game_key FROM keys_pool WHERE game_id = ? AND is_sold = 0 LIMIT 1", (game_id,))
        return cursor.fetchone()

def complete_order(user_id: int, game_id: str, key_id: int, key_value: str, price: int):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE keys_pool SET is_sold = 1 WHERE id = ?", (key_id,))
        cursor.execute(
            "INSERT INTO orders (user_id, game_id, game_key, price_paid, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, game_id, key_value, price, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()

# --- Клавиатуры ---
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Каталог игр", callback_data="catalog")],
        [InlineKeyboardButton(text="📦 Мои покупки", callback_data="my_orders"),
         InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
    ])

def catalog_categories_kb() -> InlineKeyboardMarkup:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM games")
        categories = [row[0] for row in cursor.fetchall()]

    kb = [[InlineKeyboardButton(text=f"📁 {cat}", callback_data=f"cat_{cat}")] for cat in categories]
    kb.append([InlineKeyboardButton(text="◀️ В меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def games_in_category_kb(category: str) -> InlineKeyboardMarkup:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.game_id, g.title, g.price_stars, COUNT(k.id) 
            FROM games g 
            LEFT JOIN keys_pool k ON g.game_id = k.game_id AND k.is_sold = 0 
            WHERE g.category = ? 
            GROUP BY g.game_id
        """, (category,))
        items = cursor.fetchall()

    kb = []
    for g_id, title, price, count in items:
        status = f"⭐️ {price}" if count > 0 else "❌ Закончился"
        kb.append([InlineKeyboardButton(text=f"{title} ({status})", callback_data=f"game_{g_id}")])
    kb.append([InlineKeyboardButton(text="◀️ К категориям", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def game_detail_kb(game_id: str, in_stock: bool) -> InlineKeyboardMarkup:
    buttons = []
    if in_stock:
        buttons.append([InlineKeyboardButton(text="⭐️ Оформить покупку", callback_data=f"buy_{game_id}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад в каталог", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Хэндлеры команд ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    with sqlite3.connect(DB_NAME) as conn:
        conn.cursor().execute(
            "INSERT OR IGNORE INTO users VALUES (?, ?, ?)",
            (message.from_user.id, message.from_user.username or "", datetime.now().strftime("%Y-%m-%d"))
        )
        conn.commit()

    await message.answer(
        f"👋 Привет, **{message.from_user.first_name}**!\n\n"
        "Добро пожаловать в магазин цифровых игр **Steam & Epic**.\n"
        "Оплата производится безопасно через **Telegram Stars** с моментальной выдачей ключа.",
        reply_markup=main_menu_kb(),
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        users_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        orders_count = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        revenue = c.execute("SELECT COALESCE(SUM(price_paid), 0) FROM orders").fetchone()[0]
        keys_left = c.execute("SELECT COUNT(*) FROM keys_pool WHERE is_sold = 0").fetchone()[0]

    report = (
        "📊 **Панель Администратора**\n\n"
        f"• Пользователей: `{users_count}`\n"
        f"• Всего продаж: `{orders_count}`\n"
        f"• Выручка: `⭐️ {revenue}`\n"
        f"• Ключей в наличии: `{keys_left} шт.`"
    )
    await message.answer(report, parse_mode="Markdown")

# --- Навигация и меню ---
@dp.callback_query(F.data == "to_main")
async def nav_main(call: CallbackQuery):
    await call.message.edit_text("Главное меню магазина:", reply_markup=main_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "catalog")
async def nav_catalog(call: CallbackQuery):
    await call.message.edit_text("📂 **Выберите категорию:**", reply_markup=catalog_categories_kb(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def nav_category_games(call: CallbackQuery):
    category = call.data.split("_")[1]
    await call.message.edit_text(f"🎮 **Игры в категории «{category}»:**", reply_markup=games_in_category_kb(category), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("game_"))
async def nav_game_detail(call: CallbackQuery):
    game_id = call.data.split("_")[1]
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT g.title, g.description, g.price_stars, COUNT(k.id) 
            FROM games g 
            LEFT JOIN keys_pool k ON g.game_id = k.game_id AND k.is_sold = 0 
            WHERE g.game_id = ? GROUP BY g.game_id
        """, (game_id,))
        game = c.fetchone()

    if not game:
        await call.answer("Игра не найдена", show_alert=True)
        return

    title, desc, price, count = game
    stock_label = f"✅ В наличии ({count} шт.)" if count > 0 else "❌ Нет в наличии"

    text = (
        f"🎮 **{title}**\n\n"
        f"📖 {desc}\n\n"
        f"💰 **Цена:** `⭐️ {price} Stars`\n"
        f"📦 **Наличие:** {stock_label}\n"
        f"⚡️ Доставка: моментально после подтверждения"
    )
    await call.message.edit_text(text, reply_markup=game_detail_kb(game_id, count > 0), parse_mode="Markdown")
    await call.answer()

# --- Профиль и Мои покупки ---
@dp.callback_query(F.data == "profile")
async def nav_profile(call: CallbackQuery):
    orders = get_user_orders(call.from_user.id)
    total_spent = sum(item[3] for item in orders)

    text = (
        "👤 **Ваш профиль**\n\n"
        f"• ID: `{call.from_user.id}`\n"
        f"• Куплено игр: `{len(orders)}`\n"
        f"• Потрачено звёзд: `⭐️ {total_spent}`"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="to_main")]])
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "my_orders")
async def nav_my_orders(call: CallbackQuery):
    orders = get_user_orders(call.from_user.id)
    if not orders:
        text = "📦 У вас пока нет купленных игр."
    else:
        text = "📦 **Ваша библиотека ключей:**\n\n"
        for date, title, key, price in orders:
            text += f"🎮 **{title}**\n🔑 Ключ: `{key}`\n📅 {date} (⭐️ {price})\n────────────\n"

    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="to_main")]])
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "support")
async def nav_support(call: CallbackQuery):
    back_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="to_main")]])
    await call.message.edit_text("💬 Поддержка: @telegram_support", reply_markup=back_kb)
    await call.answer()

# --- Создание счёта (Инвойса) и Закрытие ---
@dp.callback_query(F.data.startswith("buy_"))
async def create_invoice(call: CallbackQuery):
    game_id = call.data.split("_")[1]
    key_data = get_available_key(game_id)

    if not key_data:
        await call.answer("К сожалению, ключи этой игры только что закончились!", show_alert=True)
        return

    with sqlite3.connect(DB_NAME) as conn:
        game = conn.cursor().execute("SELECT title, price_stars FROM games WHERE game_id = ?", (game_id,)).fetchone()

    title, price = game

    # Инлайн-клавиатура прямо внутри инвойса: кнопка оплаты + кнопка закрытия
    invoice_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐️ Заплатить {price}", pay=True)],
            [InlineKeyboardButton(text="❌ Отмена / Закрыть", callback_data="cancel_invoice")]
        ]
    )

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"Ключ: {title}",
        description="Моментальная доставка лицензионного ключа для платформы Steam.",
        payload=f"{game_id}_{key_data[0]}",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=price)],
        provider_token="",  # Для Stars оставляем пустым
        reply_markup=invoice_kb
    )
    await call.answer()

# Обработчик кнопки «Отмена / Закрыть»
@dp.callback_query(F.data == "cancel_invoice")
async def cancel_invoice_handler(call: CallbackQuery):
    await call.message.delete()
    await call.answer("Счёт закрыт")

# --- Обработка оплаты ---
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    game_id, key_id = payload.split("_")
    price = message.successful_payment.total_amount

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        key_val = cursor.execute("SELECT game_key FROM keys_pool WHERE id = ?", (int(key_id),)).fetchone()[0]
        game_title = cursor.execute("SELECT title FROM games WHERE game_id = ?", (game_id,)).fetchone()[0]

    complete_order(message.from_user.id, game_id, int(key_id), key_val, price)

    success_text = (
        f"🎉 **Оплата принята! Спасибо за покупку!**\n\n"
        f"🎮 Игра: **{game_title}**\n"
        f"🔑 Ваш лицензионный ключ:\n`{key_val}`\n\n"
        f"_Ключ навсегда сохранен в разделе «📦 Мои покупки»._"
    )
    await message.answer(success_text, parse_mode="Markdown")

# --- Фоновый веб-сервер для Render (Health Check) ---
async def health_check(request):
    return web.Response(text="Bot is running!")

async def run_server():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- Точка входа ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await run_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
