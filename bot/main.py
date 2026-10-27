"""Точка входа Telegram-бота."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_bot_token
from bot.handlers import router


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = get_bot_token()
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    logging.info("Бот запущен. Ожидаю сообщения…")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
