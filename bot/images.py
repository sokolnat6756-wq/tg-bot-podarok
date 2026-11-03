"""Генерация фона открытки через OpenAI Images API. Ключ не логируется."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from openai import APIError, AsyncOpenAI, AuthenticationError, RateLimitError

from bot.card_compose import compose_greeting_card_image
from bot.config import (
    get_openai_api_key,
    get_openai_image_model,
    get_openai_image_quality,
    get_openai_image_size,
)

logger = logging.getLogger(__name__)

OCCASION_LABELS = {
    "birthday": "день рождения",
    "ny": "Новый год",
    "valentine": "14 февраля",
    "mar8": "8 Марта",
    "feb23": "23 Февраля",
    "wedding": "свадьба или годовщина",
    "no_reason": "тёплое поздравление без особого повода",
    "colleague": "поздравление коллеге",
}

RECIPIENT_LABELS = {
    "mom": "мама",
    "dad": "папа",
    "friend": "друг",
    "girlfriend": "подруга",
    "partner": "партнёр / пара",
    "colleague": "коллега",
    "child": "ребёнок",
    "self": "для себя",
}

AGE_LABELS = {
    "age_child": "ребёнок 3–12 лет",
    "age_teen": "подросток 13–17 лет",
    "age_young": "молодой человек 18–30 лет",
    "age_adult": "взрослый 31–50 лет",
    "age_senior": "человек старше 51 года",
}

GENDER_LABELS = {
    "male": "мужской",
    "female": "женский",
    "any": "любой",
}

INTEREST_LABELS = {
    "books": "книги",
    "tech": "техника",
    "sport": "спорт",
    "beauty": "красота",
    "home": "дом",
    "food": "еда",
    "hobby": "хобби",
}


@dataclass(frozen=True)
class CardResult:
    ok: bool
    image_bytes: bytes | None = None
    wish: str | None = None
    error: str | None = None
    retryable: bool = False


def _scene_hints(
    *,
    occasion_key: str,
    recipient_key: str,
    age_key: str,
    interest_key: str,
    birthday_years: str,
) -> str:
    bits: list[str] = []
    if recipient_key == "child" or age_key == "age_child":
        bits.append(
            "Playful child-friendly festive scene, bright soft colors, cute decorations, "
            "no scary elements, no cars-as-default cliché unless interest is tech/cars."
        )
    elif recipient_key in {"mom"} or age_key == "age_senior":
        bits.append("Elegant warm adult aesthetic, refined florals or cozy ambiance.")
    elif recipient_key in {"friend", "girlfriend", "partner"}:
        bits.append("Modern stylish celebration mood for a close person.")

    interest = INTEREST_LABELS.get(interest_key, "")
    if interest:
        bits.append(f"Subtly reflect hobby/interest atmosphere: {interest}.")

    occasion = OCCASION_LABELS.get(occasion_key, occasion_key)
    bits.append(f"Occasion-specific festive atmosphere for: {occasion}.")

    if birthday_years:
        bits.append(
            f"Birthday mood for someone turning {birthday_years}; "
            "do not paint age digits on the image."
        )
    # Открытка НЕ должна изображать конкретный предложенный подарок
    bits.append(
        "Do NOT depict any specific product gift (no basketball, gadgets, boxes as the main subject). "
        "Focus on luxurious festive atmosphere and celebration mood only. "
        "Unique creative composition — avoid repeating the same balloons/car template."
    )
    return " ".join(bits)


def build_background_prompt(
    *,
    occasion_key: str,
    recipient_key: str,
    age_key: str,
    gender_key: str,
    name: str,
    birthday_years: str = "",
    selected_gift: str = "",
    interest_key: str = "",
) -> str:
    del selected_gift  # подарок не рисуем на открытке (поле оставлено для совместимости API)
    occasion = OCCASION_LABELS.get(occasion_key, occasion_key)
    recipient = RECIPIENT_LABELS.get(recipient_key, recipient_key or "близкий человек")
    age = AGE_LABELS.get(age_key, "")
    gender = GENDER_LABELS.get(gender_key, "")
    safe_name = (name or "").strip()[:40]
    hints = _scene_hints(
        occasion_key=occasion_key,
        recipient_key=recipient_key,
        age_key=age_key,
        interest_key=interest_key,
        birthday_years=birthday_years,
    )
    age_bit = f" Age group: {age}." if age else ""
    gender_bit = f" Gender presentation: {gender}." if gender else ""
    return (
        "Create a premium luxury full-bleed vertical 9:16 greeting-card illustration. "
        "High-end colorful festive scene filling the entire frame, cinematic lighting, "
        "rich refined details, opulent celebration mood, no letterboxing, no empty borders. "
        "Keep the main subject centered; leave soft visually calm zones near the top "
        "and bottom edges for later text overlay (but still filled with scene, not blank). "
        f"Occasion: {occasion}. For: {recipient}.{age_bit}{gender_bit} "
        f"Personal dedication vibe for {safe_name or 'a loved one'}. {hints} "
        "IMPORTANT: absolutely no letters, numbers, words, signatures, logos, watermarks, "
        "or typography of any kind on the image. No celebrity faces. "
        "Do not illustrate a store product or a concrete gift item as the hero object."
    )


async def generate_greeting_card(
    *,
    occasion_key: str,
    recipient_key: str,
    age_key: str,
    gender_key: str,
    name: str,
    wish: str,
    birthday_years: str = "",
    selected_gift: str = "",
    interest_key: str = "",
) -> CardResult:
    api_key = get_openai_api_key()
    if not api_key:
        return CardResult(
            ok=False,
            error=(
                "Генерация открыток пока не настроена: нужен OPENAI_API_KEY.\n"
                "Подбор подарков кнопками работает без него."
            ),
            retryable=False,
        )

    client = AsyncOpenAI(api_key=api_key)
    model = get_openai_image_model()
    size = get_openai_image_size()
    quality = get_openai_image_quality()
    prompt = build_background_prompt(
        occasion_key=occasion_key,
        recipient_key=recipient_key,
        age_key=age_key,
        gender_key=gender_key,
        name=name,
        birthday_years=birthday_years,
        selected_gift=selected_gift,
        interest_key=interest_key,
    )

    try:
        result = await client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
            output_format="png",
        )
    except AuthenticationError:
        logger.error("OpenAI Image: ошибка авторизации (проверьте OPENAI_API_KEY)")
        return CardResult(
            ok=False,
            error="Не удалось авторизоваться в OpenAI. Проверьте ключ OPENAI_API_KEY.",
            retryable=False,
        )
    except RateLimitError:
        logger.warning("OpenAI Image: лимит запросов API")
        return CardResult(
            ok=False,
            error="Сейчас слишком много запросов к генерации. Подождите немного и нажмите «Повторить».",
            retryable=True,
        )
    except APIError as exc:
        logger.exception("OpenAI Image: ошибка API")
        detail = ""
        message = str(exc)
        if "model" in message.lower() or "not found" in message.lower():
            detail = (
                f" Возможно, модель «{model}» недоступна вашему аккаунту. "
                "В .env можно указать OPENAI_IMAGE_MODEL=gpt-image-2.5-flare "
                "или другую доступную вам image-модель."
            )
        return CardResult(
            ok=False,
            error=f"Не удалось создать открытку.{detail} Можно нажать «Повторить».",
            retryable=True,
        )
    except Exception:
        logger.exception("OpenAI Image: неожиданная ошибка")
        return CardResult(
            ok=False,
            error="Что-то пошло не так при создании открытки. Нажмите «Повторить».",
            retryable=True,
        )

    if not result.data or not getattr(result.data[0], "b64_json", None):
        return CardResult(
            ok=False,
            error="OpenAI не вернул изображение. Нажмите «Повторить».",
            retryable=True,
        )

    try:
        background = base64.b64decode(result.data[0].b64_json)
        final_png = compose_greeting_card_image(
            background,
            name=name,
            wish=wish,
            occasion_key=occasion_key,
            recipient_key=recipient_key,
            age_key=age_key,
            birthday_years=birthday_years,
            interest_key=interest_key,
            selected_gift=selected_gift,
        )
    except Exception:
        logger.exception("OpenAI Image: ошибка сборки открытки")
        return CardResult(
            ok=False,
            error="Картинку получили, но не удалось собрать открытку с текстом. Нажмите «Повторить».",
            retryable=True,
        )

    return CardResult(ok=True, image_bytes=final_png, wish=wish)
