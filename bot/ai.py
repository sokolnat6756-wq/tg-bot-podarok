"""Ответы и идеи подарков через OpenAI API. Ключ никогда не логируется."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

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
    "Ты пишешь только текст пожелания для нижней части открытки на русском. "
    "1–3 коротких предложения, тепло и естественно. "
    "НЕ начинай с имени и НЕ повторяй имя. "
    "Без эмодзи, без кавычек вокруг всего текста, без хэштегов, без подписи. "
    "Учитывай повод, возраст (если дан), кем приходится получатель и интересы. "
    "Не описывай конкретный товар-подарок. Не канцелярит. "
    "Каждый раз формулируй по-новому."
)

GIFT_SYSTEM_PROMPT = (
    "Ты эксперт по подаркам. Верни ТОЛЬКО JSON-массив из ровно 3 объектов "
    "без markdown и пояснений. Каждый объект: "
    '{"title":"название","price":"ориентир цены в рублях","why":"почему подходит"}. '
    "Учитывай бюджет, возраст, повод, интересы и роль получателя. "
    "Не повторяй идеи из списка исключений. Пиши по-русски, тепло и конкретно."
)

BUDGET_LABELS = {
    "budget_1000": "до 1 000 ₽",
    "budget_3000": "1 000–3 000 ₽",
    "budget_7000": "3 000–7 000 ₽",
    "budget_more": "от 7 000 ₽",
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

_MAX_USER_CHARS = 1500
_MAX_OUTPUT_TOKENS = 400


@dataclass(frozen=True)
class GiftSuggestResult:
    ok: bool
    ideas: list[dict[str, str]]
    error: str | None = None


def _fallback_wish(
    occasion_key: str,
    name: str,
    recipient_key: str,
    *,
    birthday_years: str = "",
    selected_gift: str = "",
    interest_key: str = "",
) -> str:
    del name  # имя только в заголовке открытки
    role = RECIPIENT_LABELS.get(recipient_key, "")
    interest = INTEREST_LABELS.get(interest_key, "")
    if occasion_key == "birthday" and birthday_years:
        base = f"Пусть этот день станет началом чудесного года. Желаю здоровья, радости и исполнения желаний."
    elif occasion_key == "birthday":
        base = "Желаю море радости, тёплых объятий и исполнения самых светлых желаний."
    elif occasion_key == "ny":
        base = "Пусть новый год принесёт лёгкость, удачу и много приятных моментов."
    else:
        occasion = OCCASION_LABELS.get(occasion_key, "праздник")
        base = f"Пусть {occasion} подарит тепло и хорошее настроение надолго."
    extras: list[str] = []
    if role == "ребёнок":
        extras.append("Пусть будет много улыбок и волшебства.")
    if interest:
        extras.append(f"И пусть рядом будет радость от любимого дела — {interest}.")
    del selected_gift  # товар на открытке не обыгрываем
    return " ".join([base, *extras[:2]])


def _answers_brief(answers: dict[str, str]) -> str:
    lines = [
        f"Кому: {RECIPIENT_LABELS.get(answers.get('recipient', ''), answers.get('recipient', ''))}",
        f"Пол: {GENDER_LABELS.get(answers.get('gender', ''), answers.get('gender', ''))}",
        f"Возрастной диапазон: {AGE_LABELS.get(answers.get('age', ''), answers.get('age', ''))}",
        f"Повод: {OCCASION_LABELS.get(answers.get('occasion', ''), answers.get('occasion', ''))}",
        f"Бюджет: {BUDGET_LABELS.get(answers.get('budget', ''), answers.get('budget', ''))}",
        f"Интересы: {INTEREST_LABELS.get(answers.get('interest', ''), answers.get('interest', ''))}",
    ]
    years = (answers.get("birthday_years") or "").strip()
    if years:
        lines.append(f"Исполняется лет: {years}")
    return "\n".join(lines)


def _parse_ideas(raw: str) -> list[dict[str, str]]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    ideas: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        price = str(item.get("price") or "").strip()
        why = str(item.get("why") or "").strip()
        if title and why:
            ideas.append({"title": title[:120], "price": price[:80] or "по бюджету", "why": why[:300]})
        if len(ideas) >= 3:
            break
    return ideas


def format_ideas_text(ideas: list[dict[str, str]]) -> str:
    lines = ["Вот идеи подарков специально для вас:\n"]
    for i, idea in enumerate(ideas, start=1):
        lines.append(
            f"{i}. {idea['title']} — {idea.get('price', 'по бюджету')}\n"
            f"   Почему подходит: {idea['why']}\n"
        )
    lines.append(
        "Можете воспользоваться любой идеей на свой вкус.\n"
        "Если хотите — создадим персональную открытку или запросим ещё идеи."
    )
    return "\n".join(lines)


async def suggest_gifts_with_ai(
    answers: dict[str, str],
    *,
    exclude_titles: list[str] | None = None,
) -> GiftSuggestResult:
    api_key = get_openai_api_key()
    if not api_key:
        return GiftSuggestResult(
            ok=False,
            ideas=[],
            error=(
                "Не удалось подобрать идеи: не задан OPENAI_API_KEY.\n"
                "Добавьте ключ и нажмите «Повторить подбор»."
            ),
        )

    exclude = exclude_titles or []
    exclude_block = ", ".join(exclude[-30:]) if exclude else "нет"
    user_prompt = (
        f"{_answers_brief(answers)}\n\n"
        f"Уже предлагали (не повторять): {exclude_block}\n"
        "Дай 3 новые идеи."
    )
    client = AsyncOpenAI(api_key=api_key)
    try:
        response = await client.chat.completions.create(
            model=get_openai_model(),
            messages=[
                {"role": "system", "content": GIFT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=700,
        )
    except AuthenticationError:
        logger.error("OpenAI gifts: ошибка авторизации")
        return GiftSuggestResult(
            ok=False,
            ideas=[],
            error="Не удалось подключиться к OpenAI. Проверьте ключ и нажмите «Повторить подбор».",
        )
    except RateLimitError:
        logger.warning("OpenAI gifts: лимит")
        return GiftSuggestResult(
            ok=False,
            ideas=[],
            error="Сейчас слишком много запросов к нейросети. Подождите немного и нажмите «Повторить подбор».",
        )
    except (APIError, Exception):
        logger.exception("OpenAI gifts: ошибка API")
        return GiftSuggestResult(
            ok=False,
            ideas=[],
            error="Сейчас не удалось получить идеи от нейросети. Нажмите «Повторить подбор».",
        )

    raw = response.choices[0].message.content if response.choices else ""
    ideas = _parse_ideas(raw or "")
    if len(ideas) < 1:
        return GiftSuggestResult(
            ok=False,
            ideas=[],
            error="Нейросеть ответила в неожиданном формате. Нажмите «Повторить подбор».",
        )
    return GiftSuggestResult(ok=True, ideas=ideas)


async def compose_greeting_wish(
    *,
    name: str,
    occasion_key: str,
    recipient_key: str,
    age_key: str,
    gender_key: str,
    birthday_years: str = "",
    selected_gift: str = "",
    interest_key: str = "",
) -> str:
    fallback = _fallback_wish(
        occasion_key,
        name,
        recipient_key,
        birthday_years=birthday_years,
        selected_gift=selected_gift,
        interest_key=interest_key,
    )
    api_key = get_openai_api_key()
    if not api_key:
        return fallback

    prompt = (
        "Напиши только пожелание (без имени в начале).\n"
        f"Имя уже будет в заголовке: {name or 'не указано'}\n"
        f"Кем приходится: {RECIPIENT_LABELS.get(recipient_key, recipient_key) or 'не указано'}\n"
        f"Пол: {GENDER_LABELS.get(gender_key, gender_key) or 'не указано'}\n"
        f"Возрастной диапазон: {AGE_LABELS.get(age_key, age_key) or 'не указано'}\n"
        f"Сколько лет исполняется: {birthday_years or 'не указано'}\n"
        f"Повод: {OCCASION_LABELS.get(occasion_key, occasion_key)}\n"
        f"Интересы: {INTEREST_LABELS.get(interest_key, interest_key) or 'не указано'}\n"
        f"Выбранный подарок: {selected_gift or 'не указан'}\n"
        "Не выдумывай факты, которых нет в списке."
    )
    client = AsyncOpenAI(api_key=api_key)
    try:
        response = await client.chat.completions.create(
            model=get_openai_model(),
            messages=[
                {"role": "system", "content": WISH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=120,
        )
        text = (response.choices[0].message.content or "").strip().strip("«»\"'")
        return text[:280] if text else fallback
    except Exception:
        logger.exception("OpenAI: не удалось сочинить поздравление, используем запасной текст")
        return fallback


async def reply_with_openai(user_text: str) -> str:
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
            max_completion_tokens=_MAX_OUTPUT_TOKENS,
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
