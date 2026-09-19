import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# Читаем токен из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Ошибка: переменная окружения BOT_TOKEN не задана!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- База данных игр ---
GAMES = {
    "cp2077": {
        "title": "Cyberpunk 2077: Phantom Liberty",
        "price": 1990,
        "description": "Экшен-RPG в открытом мире Найт-Сити с дополнением.",
        "key": "CP77-XXXXX-YYYYY-ZZZZZ"
    },
    "er": {
        "title": "Elden Ring: Shadow of the Erdtree",
        "price": 2490,
        "description": "Мрачное темное фэнтези от FromSoftware и Джорджа Мартина.",
        "key": "ELDEN-AAAAA-BBBBB-CCCCC"
    },
    "bg3": {
        "title": "Baldur's Gate 3",
        "price": 2190,
        "description": "Партийная ролевая игра нового поколения по вселенной D&D.",
        "key": "BG3-11111-22222-33333"
    },
    "gta5": {
        "title": "Grand Theft Auto V: Premium Edition",
        "price": 990,
        "description": "Легендарный криминальный экшен в открытом мире Лос-Сантоса.",
        "key": "GTA5-99999-88888-77777"
    }
}

# --- Клавиатуры ---
def get_main_menu_kb() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🎮 Каталог игр", callback_data="catalog")],
        [InlineKeyboardButton(text="ℹ️ О нас", callback_data="about"),
         InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_catalog_kb() -> InlineKeyboardMarkup:
    buttons = []
    for game_id, data in GAMES.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{data['title']} — {data['price']} ₽",
                callback_data=f"game_{game_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀️ В главное меню", callback_data="to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_game_card_kb(game_id: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="💳 Купить", callback_data=f"buy_{game_id}")],
        [InlineKeyboardButton(text="◀️ Назад в каталог", callback_data="catalog")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- Обработчики aiogram ---
@dp.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в магазин цифровых ключей игр.\n"
        "Выбирай игру в каталоге и забирай ключ сразу после покупки!"
    )
    await message.answer(text, reply_markup=get_main_menu_kb())

@dp.callback_query(F.data == "to_main")
async def back_to_main(call: CallbackQuery):
    await call.message.edit_text("Главное меню магазина:", reply_markup=get_main_menu_kb())
    await call.answer()

@dp.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    await call.message.edit_text(
        "🔥 **Каталог доступных игр:**\nВыберите нужную позицию:",
        reply_markup=get_catalog_kb(),
        parse_mode="Markdown"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("game_"))
async def show_game(call: CallbackQuery):
    game_id = call.data.split("_")[1]
    game = GAMES.get(game_id)

    if not game:
        await call.answer("Игра не найдена!", show_alert=True)
        return

    card_text = (
        f"🎮 *{game['title']}*\n\n"
        f"📝 {game['description']}\n\n"
        f"💰 **Цена:** `{game['price']} ₽`\n"
        f"⚡️ Доставка: моментально"
    )
    await call.message.edit_text(card_text, reply_markup=get_game_card_kb(game_id), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def process_purchase(call: CallbackQuery):
    game_id = call.data.split("_")[1]
    game = GAMES.get(game_id)

    if not game:
        await call.answer("Ошибка при оформлении.", show_alert=True)
        return

    success_text = (
        f"🎉 **Оплата успешно завершена!**\n\n"
        f"Игра: *{game['title']}*\n"
        f"Ключ активации (Steam):\n"
        f"🔑 `{game['key']}`\n\n"
        f"_Скопируйте ключ и активируйте в аккаунте._"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎮 Вернуться в каталог", callback_data="catalog")]]
    )
    await call.message.edit_text(success_text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer("Товар выдан!")

@dp.callback_query(F.data == "about")
async def about_info(call: CallbackQuery):
    text = (
        "🛡 **О магазине GameStore**\n\n"
        "• Моментальная выдача ключей\n"
        "• 100% гарантия валидности\n"
        "• Техподдержка 24/7"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="to_main")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "support")
async def support_info(call: CallbackQuery):
    text = "💬 Если возникли вопросы или проблемы, напишите: @support_username"
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="to_main")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb)
    await call.answer()

# --- Веб-сервер для Render (Health Check) ---
async def health_check(request):
    return web.Response(text="Bot is running!")

async def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- Запуск приложения ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запускается...")

    # Запуск фонового веб-сервера для Render
    await run_dummy_server()

    # Сброс зависших апдейтов и запуск Polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
