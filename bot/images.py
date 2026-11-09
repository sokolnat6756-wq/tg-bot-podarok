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

# Настроение интереса — только предметы и свет, без человека, который этим занимается.
_INTEREST_STILL_LIFE = {
    "books": "a few beautiful closed books and warm library light, no reader",
    "tech": "sleek refined objects and a soft glow, no person holding a device",
    "sport": "elegant sense of motion in light and color only, no athlete",
    "beauty": "flowers, silk and a perfume bottle, no face and no one applying makeup",
    "home": "a beautiful empty interior, no occupant",
    "food": "an exquisite untouched table, no diner, no hands, no one drinking",
    "hobby": "tasteful crafted objects, no person making them",
}

_OCCASION_SCENES = {
    "birthday": (
        "Birthday still life: an unattended celebration cake, flowers, candles and warm light. "
        "No guest, no person blowing out candles."
    ),
    "valentine": (
        "Romantic luxury still life: roses, candlelight, silk and gold. "
        "No couple and no people."
    ),
    "mar8": (
        "Luxury spring still life for Women's Day: peonies, tulips, silk ribbons, "
        "soft gold light, marble and delicate glass. "
        "No woman, no seated person, no one holding a cup of coffee or tea."
    ),
    "feb23": (
        "Noble festive still life in deep blue and gold, with formal ribbons and stars. "
        "No soldiers, no men, no portraits."
    ),
    "wedding": (
        "Elegant ceremony atmosphere: flowers and rings as a still life. "
        "No bride, no groom, no guests."
    ),
    "colleague": (
        "Refined festive still life with flowers and warm light. "
        "No coworker and no person at a desk."
    ),
    "no_reason": "Warm luxury still life of flowers and light, with no people.",
}

_NO_REAL_PEOPLE = (
    "FORBIDDEN: real people and ordinary humans of any age or gender. "
    "No portraits, faces, eyes, hands, bodies, silhouettes, or lifestyle scenes "
    "of someone sitting, standing, walking, posing, celebrating, or drinking coffee or tea. "
    "Do not draw the recipient, a friend, a woman, a man, or a child. "
    "Do not invent a person to stand in for the name on the card. "
    "The picture is a premium festive still life, not a photograph of a human."
)


@dataclass(frozen=True)
class CardResult:
    ok: bool
    image_bytes: bytes | None = None
    wish: str | None = None
    error: str | None = None
    retryable: bool = False


def _style_without_people(recipient_key: str, age_key: str) -> str:
    """Настроение по поводу, но никогда не просьба нарисовать человека."""
    if recipient_key == "child" or age_key == "age_child":
        return (
            "Playful festive décor, bright soft colors, cute decorations and toys. "
            "No scary elements and no child in the picture."
        )
    if recipient_key in {"mom", "girlfriend"} or age_key == "age_senior":
        return "Elegant refined florals, silk and warm light. No woman and no person."
    return "Modern luxurious festive still life. No people."


def _new_year_scene() -> str:
    return (
        "Premium colorful New Year interior, like an expensive greeting card. "
        "Fill the frame with only these subjects: a large decorated Christmas tree "
        "with ornaments, lights, garlands and baubles; a glowing fireplace; "
        "wrapped gift boxes under the tree; Ded Moroz or Santa Claus in a full traditional costume; "
        "Snegurochka may stand beside him, also in a fairy-tale costume; "
        "a festive rabbit and a small penguin or squirrel may sit in the snow as decoration. "
        "Ded Moroz or Santa is a storybook character in costume, not a photograph of a real man. "
        "The foreground is the tree, the gifts and those characters. "
        "There is no room for anyone else."
    )


def _scene_hints(
    *,
    occasion_key: str,
    recipient_key: str,
    age_key: str,
    interest_key: str,
    birthday_years: str,
) -> str:
    bits: list[str] = []
    if occasion_key == "ny":
        bits.append(
            "Luxurious colorful winter celebration. "
            "Ordinary people are not allowed; only the holiday characters named below."
        )
        bits.append(_new_year_scene())
    else:
        bits.append(_style_without_people(recipient_key, age_key))
        bits.append(
            _OCCASION_SCENES.get(
                occasion_key,
                "Luxurious festive still life for the occasion, with no people.",
            )
        )
        bits.append("No Santa, no Ded Moroz, no Snegurochka, and no ordinary people.")

    still_life = _INTEREST_STILL_LIFE.get(interest_key, "")
    if still_life:
        bits.append(f"A subtle still-life accent only: {still_life}.")

    if birthday_years:
        bits.append(
            "Birthday atmosphere only. Do not paint the age as digits and do not show a person."
        )
    # Открытка НЕ должна изображать конкретный предложенный подарок
    bits.append(
        "Do NOT depict any specific product gift (no basketball, gadgets, boxes as the main subject, "
        "except wrapped holiday gifts on a New Year card). "
        "Focus on a luxurious festive atmosphere. "
        "Unique creative composition — avoid repeating the same balloons or car template."
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
    # Имя, пол и роль не отдаём модели как персонажа: из-за этого она рисовала
    # случайную женщину вместо праздничной открытки. Текст имени накладывается отдельно.
    del name, gender_key, selected_gift
    occasion = OCCASION_LABELS.get(occasion_key, occasion_key)
    if occasion_key == "ny":
        people_rule = (
            "ABSOLUTE RULE: this picture contains no real people and no children. "
            "No boy, no girl, no baby, no kid in a hat or scarf, no child smiling, "
            "no child holding a snow globe, gift, or toy. "
            "No photorealistic human face except the fairy-tale faces of Ded Moroz "
            "or Santa and, if present, Snegurochka. No guests, no portrait of the recipient."
        )
    else:
        people_rule = _NO_REAL_PEOPLE
    if occasion_key == "ny":
        product_rule = (
            "Wrapped holiday gift boxes belong near the tree, "
            "but do not turn one store product into the hero."
        )
    else:
        product_rule = (
            "Do not illustrate a store product or a concrete gift item as the hero object."
        )
    hints = _scene_hints(
        occasion_key=occasion_key,
        recipient_key=recipient_key,
        age_key=age_key,
        interest_key=interest_key,
        birthday_years=birthday_years,
    )
    return (
        f"{people_rule} "
        "Do not draw a boy, a girl, or any child, including a child in winter clothes "
        "holding a snow globe, a gift, or a cup. "
        "Create a premium luxury full-bleed vertical 9:16 greeting-card illustration. "
        "High-end colorful festive scene filling the entire frame, cinematic lighting, "
        "rich refined details, opulent celebration mood, no letterboxing, no empty borders. "
        "Keep the festive scene centered; leave soft visually calm zones near the top "
        "and bottom edges for later text overlay (but still filled with scene, not blank). "
        f"Occasion mood only, not a person to draw: {occasion}. {hints} "
        "IMPORTANT: absolutely no letters, numbers, words, signatures, logos, watermarks, "
        "or typography of any kind on the image. "
        f"{product_rule}"
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
