"""Настройки бота. Секреты читаются только из переменных окружения."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Локально подхватываем .env рядом с проектом (если есть)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

_DEFAULT_OPENAI_MODEL = "gpt-6-luna"
# Предпочтительная модель из ТЗ. Доступ к аккаунту здесь не проверялся.
_DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-2"
_DEFAULT_IMAGE_SIZE = "1024x1536"
_DEFAULT_IMAGE_QUALITY = "medium"
_DEFAULT_CARD_WIDTH = 1080
_DEFAULT_CARD_HEIGHT = 1920
_DEFAULT_CARD_USER_LIMIT = 2


def get_bot_token() -> str:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "вставьте_токен_сюда":
        raise RuntimeError(
            "Не задан BOT_TOKEN. Создайте файл .env по образцу .env.example "
            "или задайте переменную окружения BOT_TOKEN."
        )
    return token


def get_openai_api_key() -> str | None:
    """Ключ OpenAI. None — если не задан (опрос кнопками продолжит работать)."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key.startswith("вставьте"):
        return None
    return key


def get_openai_model() -> str:
    model = os.getenv("OPENAI_MODEL", _DEFAULT_OPENAI_MODEL).strip()
    return model or _DEFAULT_OPENAI_MODEL


def get_openai_image_model() -> str:
    model = os.getenv("OPENAI_IMAGE_MODEL", _DEFAULT_OPENAI_IMAGE_MODEL).strip()
    return model or _DEFAULT_OPENAI_IMAGE_MODEL


def get_openai_image_size() -> str:
    size = os.getenv("OPENAI_IMAGE_SIZE", _DEFAULT_IMAGE_SIZE).strip()
    return size or _DEFAULT_IMAGE_SIZE


def get_openai_image_quality() -> str:
    quality = os.getenv("OPENAI_IMAGE_QUALITY", _DEFAULT_IMAGE_QUALITY).strip()
    return quality or _DEFAULT_IMAGE_QUALITY


def get_card_output_size() -> tuple[int, int]:
    """Итоговый холст открытки 9:16 (по умолчанию 1080×1920)."""
    try:
        width = int(os.getenv("CARD_OUTPUT_WIDTH", str(_DEFAULT_CARD_WIDTH)))
        height = int(os.getenv("CARD_OUTPUT_HEIGHT", str(_DEFAULT_CARD_HEIGHT)))
    except ValueError:
        return _DEFAULT_CARD_WIDTH, _DEFAULT_CARD_HEIGHT
    if width < 256 or height < 256:
        return _DEFAULT_CARD_WIDTH, _DEFAULT_CARD_HEIGHT
    return width, height


def get_card_user_limit() -> int:
    """Сколько готовых открыток можно создать одному пользователю. 0 = без лимита."""
    raw = os.getenv("CARD_USER_LIMIT", str(_DEFAULT_CARD_USER_LIMIT)).strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_CARD_USER_LIMIT
    return max(0, value)
