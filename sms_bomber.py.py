import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

# Включаем логирование, чтобы видеть события и ошибки в консоли
logging.basicConfig(level=logging.INFO)

# Замените 'YOUR_BOT_TOKEN' на токен, полученный от @BotFather
BOT_TOKEN = "8946562478:AAErgPPJBfldwhrFh4--BZpBCfll9T5jjbE"

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хэндлер на команду /start
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! Я базовый бот на aiogram 3.\n"
        "Напиши мне что-нибудь, и я отвечу эхом."
    )

# Хэндлер на команду /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Доступные команды:\n"
        "/start - Перезапустить бота\n"
        "/help - Показать это меню"
    )

# Хэндлер для любых текстовых сообщений (эхо)
@dp.message()
async def echo_message(message: Message):
    # Отправляем пользователю его же текст
    await message.answer(f"Ты написал: {message.text}")

async def main():
    # Пропускаем старые обновления, накопившиеся, пока бот был выключен
    await bot.delete_webhook(drop_pending_updates=True)
    # Запускаем поллинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")