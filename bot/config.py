"""Настройки бота. Токен берётся только из переменных окружения."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Локально подхватываем .env рядом с проектом (если есть)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def get_bot_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "вставьте_токен_сюда":
        raise RuntimeError(
            "Не задан BOT_TOKEN. Создайте файл .env по образцу .env.example "
            "или задайте переменную окружения BOT_TOKEN."
        )
    return token
