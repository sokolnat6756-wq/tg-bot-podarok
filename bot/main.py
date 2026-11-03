"""Точка входа Telegram-бота (polling) + HTTP health для App Platform."""

from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import get_bot_token
from bot.handlers import router


async def _health(_request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def _start_health_server() -> web.AppRunner:
    """Timeweb App Platform часто проверяет HTTP-порт (PORT)."""
    port = int(os.getenv("PORT", "8080"))
    app = web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("Health-check слушает 0.0.0.0:%s", port)
    return runner


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

    health_runner = await _start_health_server()
    logging.info("Бот запущен (polling). Ожидаю сообщения…")
    try:
        await dp.start_polling(bot)
    finally:
        await health_runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
