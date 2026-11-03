"""Ответы через OpenAI API. Ключ никогда не логируется."""

from __future__ import annotations

import logging

from openai import APIError, AsyncOpenAI, AuthenticationError, RateLimitError

from bot.config import get_openai_api_key, get_openai_model
from bot.images import (
    AGE_LABELS,
    GENDER_LABELS,
    OCCASION_LABELS,
    RECIPIENT_LABELS,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты дружелюбный помощник по выбору подарков. Отвечай на русском, "
    "тепло и коротко (обычно 2–5 предложений). Предлагай конкретные идеи "
    "с учётом бюджета, возраста и интересов, если человек их назвал. "
    "Не выдумывай цены магазинов как точные факты — говори ориентировочно. "
    "Если вопрос не про подарки, вежливо верни разговор к идеям подарков."
)

WISH_SYSTEM_PROMPT = (
    "Ты пишешь короткие тёплые поздравления на русском для открытки. "
    "1–2 предложения, без эмодзи, без кавычек вокруг всего текста, "
    "без хэштегов, без подписи автора. Учитывай возраст, повод и кем "
    "приходиться получатель. Не используй канцелярит."
)

# Ограничения, чтобы контролировать стоимость
_MAX_USER_CHARS = 1500
_MAX_OUTPUT_TOKENS = 400


def _fallback_wish(occasion_key: str, name: str, recipient_key: str) -> str:
    occasion = OCCASION_LABELS.get(occasion_key, "праздник")
    who = name.strip() or RECIPIENT_LABELS.get(recipient_key, "друг")
    return (
        f"{who}, поздравляю с праздником — {occasion}! "
        "Желаю тепла, радости и всего самого светлого."
    )


async def compose_greeting_wish(
    *,
    name: str,
    occasion_key: str,
    recipient_key: str,
    age_key: str,
    gender_key: str,
) -> str:
    """Короткое поздравление; при сбое API — аккуратный запасной текст."""
    api_key = get_openai_api_key()
    fallback = _fallback_wish(occasion_key, name, recipient_key)
    if not api_key:
        return fallback

    prompt = (
        f"Имя на открытке: {name or 'друг'}\n"
        f"Кем приходится: {RECIPIENT_LABELS.get(recipient_key, recipient_key)}\n"
        f"Пол: {GENDER_LABELS.get(gender_key, gender_key)}\n"
        f"Возраст: {AGE_LABELS.get(age_key, age_key)}\n"
        f"Повод: {OCCASION_LABELS.get(occasion_key, occasion_key)}\n"
        "Сформулируй поздравление."
    )
    client = AsyncOpenAI(api_key=api_key)
    try:
        response = await client.chat.completions.create(
            model=get_openai_model(),
            messages=[
                {"role": "system", "content": WISH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
            temperature=0.8,
        )
        text = (response.choices[0].message.content or "").strip().strip("«»\"'")
        return text[:280] if text else fallback
    except Exception:
        logger.exception("OpenAI: не удалось сочинить поздравление, используем запасной текст")
        return fallback


async def reply_with_openai(user_text: str) -> str:
    """Возвращает ответ модели или понятное сообщение об ошибке/настройке."""
    api_key = get_openai_api_key()
    if not api_key:
        return (
            "Текстовый помощник пока не настроен.\n"
            "Нажмите «Подобрать подарок» — подбор по кнопкам работает как раньше."
        )

    model = get_openai_model()
    client = AsyncOpenAI(api_key=api_key)
    safe_text = (user_text or "").strip()[:_MAX_USER_CHARS]
    if not safe_text:
        return "Напишите вопрос текстом или нажмите «Подобрать подарок»."

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": safe_text},
            ],
            max_tokens=_MAX_OUTPUT_TOKENS,
            temperature=0.7,
        )
    except AuthenticationError:
        logger.error("OpenAI: ошибка авторизации (проверьте OPENAI_API_KEY)")
        return (
            "Не удалось подключиться к помощнику. "
            "Проверьте ключ OpenAI или воспользуйтесь кнопкой «Подобрать подарок»."
        )
    except RateLimitError:
        logger.warning("OpenAI: превышен лимит запросов")
        return "Сейчас слишком много запросов. Подождите немного или выберите подарок кнопками."
    except APIError:
        logger.exception("OpenAI: ошибка API")
        return (
            "Помощник временно недоступен. "
            "Попробуйте позже или нажмите «Подобрать подарок»."
        )
    except Exception:
        logger.exception("OpenAI: неожиданная ошибка")
        return (
            "Что-то пошло не так при ответе. "
            "Нажмите «Подобрать подарок» — этот режим работает без OpenAI."
        )

    choice = response.choices[0].message.content if response.choices else None
    text = (choice or "").strip()
    if not text:
        return "Не получилось сформулировать ответ. Попробуйте перефразировать вопрос."
    return text
