"""Обработчики команд и кнопок.

Правильный порядок подбора подарка:
1) опрос (для ДР — ещё сколько лет исполняется)
2) идеи через ИИ + ожидание
3) выбор подарка из списка
4) только потом предложение открытки
"""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.ai import (
    compose_greeting_wish,
    format_ideas_text,
    reply_with_openai,
    suggest_gifts_with_ai,
)
from bot.images import generate_greeting_card
from bot.keyboards import (
    STEP_KEYBOARDS,
    STEP_PROMPTS,
    card_offer_kb,
    card_result_kb,
    ideas_kb,
    main_menu,
    retry_ideas_kb,
)
from bot.limits import card_guard
from bot.session import store

router = Router()

WAITING_TEXT = (
    "🎁 Подбираю идеи специально для вас…\n"
    "Я работаю, пожалуйста, немного подождите ✨"
)

WELCOME = (
    "Привет! Я помогу быстро подобрать идеальный подарок "
    "и при желании сделать персональную поздравительную открытку.\n\n"
    "Нажмите «Подобрать подарок», ответьте на вопросы — я предложу идеи. "
    "После идей можно сразу создать открытку.\n\n"
    "Отдельную открытку без подбора можно сделать кнопкой «Сделать открытку»."
)


def _parse_birthday_years(text: str) -> int | None:
    cleaned = (text or "").strip()
    match = re.search(r"(\d{1,3})", cleaned)
    if not match:
        return None
    value = int(match.group(1))
    if 1 <= value <= 120:
        return value
    return None


async def _ask_next_card_context(message: Message, user_id: int) -> None:
    """Только для отдельного сценария открытки или после выбора подарка."""
    session = store.get(user_id)
    if not session.can_generate_card() and not session.card_standalone:
        await message.answer(
            "Сначала получите идеи подарков.",
            reply_markup=main_menu(),
        )
        return

    missing = session.next_missing_card_context()
    if missing is None:
        await _run_card_generation(message, user_id)
        return

    session.step = missing
    if missing == "card_name":
        await message.answer(
            "Как зовут человека, для которого открытка? Напишите имя.",
            reply_markup=main_menu(),
        )
        return
    if missing == "birthday_years":
        await message.answer(
            "Сколько лет исполняется имениннику? Напишите число, например: 30"
        )
        return
    await message.answer(
        STEP_PROMPTS[missing],
        reply_markup=STEP_KEYBOARDS[missing](),
    )


async def _run_card_generation(message: Message, user_id: int) -> None:
    session = store.get(user_id)
    if not session.can_generate_card():
        await message.answer(
            "Сначала получите идеи подарков — потом сделаем открытку.",
            reply_markup=main_menu(),
        )
        return

    blocked = card_guard.begin(user_id)
    if blocked:
        await message.answer(blocked, reply_markup=main_menu())
        return

    wait_msg = await message.answer(
        "✨ Создаю персональную открытку. Это займёт немного времени,\n"
        "пожалуйста, подождите…"
    )
    try:
        await message.bot.send_chat_action(message.chat.id, action="upload_photo")

        name = session.context_value("card_name") or "Друг"
        occasion = session.context_value("occasion", "no_reason")
        recipient = session.context_value("recipient", "friend")
        age = session.context_value("age", "")
        gender = session.context_value("gender", "")
        birthday_years = session.context_value("birthday_years", "")
        interest = session.context_value("interest", "")
        # Подарок на открытку не переносим (идеи — отдельно; «где купить» — на будущее)

        wish = await compose_greeting_wish(
            name=name,
            occasion_key=occasion,
            recipient_key=recipient,
            age_key=age,
            gender_key=gender,
            birthday_years=birthday_years,
            selected_gift="",
            interest_key=interest,
        )
        session.card_answers["card_wish"] = wish

        result = await generate_greeting_card(
            occasion_key=occasion,
            recipient_key=recipient,
            age_key=age,
            gender_key=gender,
            name=name,
            wish=wish,
            birthday_years=birthday_years,
            selected_gift="",
            interest_key=interest,
        )
        if not result.ok or not result.image_bytes:
            try:
                await wait_msg.edit_text(
                    result.error or "Не удалось создать открытку. Нажмите «Повторить»."
                )
            except Exception:
                await message.answer(
                    result.error or "Не удалось создать открытку.",
                    reply_markup=card_result_kb(),
                )
                return
            await message.answer("Можно попробовать ещё раз:", reply_markup=card_result_kb())
            return

        try:
            await wait_msg.delete()
        except Exception:
            try:
                await wait_msg.edit_text("Готово ✨")
            except Exception:
                pass

        photo = BufferedInputFile(result.image_bytes, filename="greeting_card.png")
        await message.answer_photo(
            photo=photo,
            caption="Ваша персональная открытка готова — можно сохранить и отправить ✨",
            reply_markup=card_result_kb(),
        )
        card_guard.commit(user_id)
        session.step = "card_done"
    except Exception:
        try:
            await wait_msg.edit_text(
                "Не удалось создать открытку из‑за ошибки. Нажмите «Повторить»."
            )
        except Exception:
            await message.answer(
                "Не удалось создать открытку из‑за ошибки.",
                reply_markup=card_result_kb(),
            )
        else:
            await message.answer("Можно попробовать ещё раз:", reply_markup=card_result_kb())
    finally:
        card_guard.end(user_id)


async def _fetch_and_show_ideas(message: Message, user_id: int) -> None:
    """Генерация идей подарков. Открытка здесь не создаётся."""
    session = store.get(user_id)
    session.mode = "gift"
    session.card_standalone = False
    session.step = "results"

    wait_msg = await message.answer(WAITING_TEXT)
    session.waiting_message_id = wait_msg.message_id
    await message.bot.send_chat_action(message.chat.id, action="typing")

    result = await suggest_gifts_with_ai(
        session.answers,
        exclude_titles=session.shown_titles,
    )

    if not result.ok or not result.ideas:
        text = result.error or "Сейчас не удалось получить идеи. Нажмите «Повторить подбор»."
        try:
            await wait_msg.edit_text(text, reply_markup=retry_ideas_kb())
        except Exception:
            await message.answer(text, reply_markup=retry_ideas_kb())
        return

    session.remember_ideas(result.ideas)
    session.step = "card_offer"
    text = format_ideas_text(result.ideas)
    try:
        await wait_msg.edit_text(text, reply_markup=ideas_kb())
    except Exception:
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer(text, reply_markup=ideas_kb())


async def _continue_gift_quiz_after_birthday(message: Message, user_id: int) -> None:
    """После возраста ДР — дальше бюджет, не открытка."""
    session = store.get(user_id)
    session.mode = "gift"
    session.card_standalone = False
    session.step = "budget"
    await message.answer(
        STEP_PROMPTS["budget"],
        reply_markup=STEP_KEYBOARDS["budget"](),
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    session = store.get(message.from_user.id)
    session.reset()
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(F.text.in_({"🎁 Подобрать подарок", "Подобрать подарок"}))
async def start_quiz(message: Message) -> None:
    session = store.get(message.from_user.id)
    session.start_quiz()
    await message.answer(
        STEP_PROMPTS[session.step],
        reply_markup=STEP_KEYBOARDS[session.step](),
    )


async def _reject_if_card_limit(message: Message, user_id: int) -> bool:
    text = card_guard.limit_message(user_id)
    if not text:
        return False
    await message.answer(text, reply_markup=main_menu())
    return True


@router.message(F.text.in_({"🖼 Сделать открытку", "Сделать открытку"}))
async def start_card(message: Message) -> None:
    if await _reject_if_card_limit(message, message.from_user.id):
        return
    session = store.get(message.from_user.id)
    session.start_card_standalone()
    await _ask_next_card_context(message, message.from_user.id)


@router.callback_query(F.data.startswith("gift:"))
async def on_gift_select(callback: CallbackQuery) -> None:
    """Старые кнопки «Выбрать идею N» — выбор больше не нужен, сразу к открытке."""
    session = store.get(callback.from_user.id)
    await callback.answer()
    if session.last_ideas:
        session.ready_for_card = True
        session.step = "card_offer"
    await callback.message.answer(
        "Создадим персональную открытку?",
        reply_markup=card_offer_kb(),
    )


@router.callback_query(F.data.startswith("action:"))
async def on_action(callback: CallbackQuery) -> None:
    action = callback.data.split(":", 1)[1]
    session = store.get(callback.from_user.id)
    await callback.answer()

    if action == "restart":
        session.start_quiz()
        await callback.message.answer(
            STEP_PROMPTS[session.step],
            reply_markup=STEP_KEYBOARDS[session.step](),
        )
        return

    if action == "more":
        if not session.quiz_complete():
            await callback.message.answer(
                "Сначала пройдите короткий опрос до конца кнопкой «Подобрать подарок».",
                reply_markup=main_menu(),
            )
            return
        await _fetch_and_show_ideas(callback.message, callback.from_user.id)
        return

    if action == "card_yes":
        if await _reject_if_card_limit(callback.message, callback.from_user.id):
            return
        if not session.can_generate_card():
            await callback.message.answer(
                "Сначала получите идеи подарков кнопкой «Подобрать подарок».",
                reply_markup=main_menu(),
            )
            return
        session.mode = "card"
        # после идей открытка идёт без привязки к номеру подарка
        session.card_standalone = session.card_standalone and not session.ready_for_card
        if session.ready_for_card:
            session.card_standalone = False
        session.step = "card_name"
        await callback.message.answer(
            "Как зовут человека, для которого открытка? Напишите имя.",
            reply_markup=main_menu(),
        )
        return

    if action == "card_skip":
        session.step = "done"
        await callback.message.answer(
            "Хорошо! Если понадобится открытка позже — нажмите «Сделать открытку».",
            reply_markup=main_menu(),
        )
        return

    if action == "card_retry":
        if await _reject_if_card_limit(callback.message, callback.from_user.id):
            return
        if not session.can_generate_card() or not session.context_value("card_name"):
            await callback.message.answer(
                "Недостаточно данных для повтора. Выберите подарок или нажмите «Сделать открытку».",
                reply_markup=main_menu(),
            )
            return
        await _run_card_generation(callback.message, callback.from_user.id)
        return

    if action == "card_again":
        if await _reject_if_card_limit(callback.message, callback.from_user.id):
            return
        session.start_card_standalone()
        await _ask_next_card_context(callback.message, callback.from_user.id)
        return


@router.callback_query(F.data.contains(":"))
async def on_answer(callback: CallbackQuery) -> None:
    try:
        key, value = callback.data.split(":", 1)
    except ValueError:
        await callback.answer()
        return

    if key not in STEP_PROMPTS:
        await callback.answer()
        return

    session = store.get(callback.from_user.id)

    # --- Отдельный сценарий открытки (кнопка «Сделать открытку») ---
    if session.card_standalone and session.mode == "card":
        if session.step != key:
            await callback.answer("Сначала ответьте на текущий вопрос.", show_alert=True)
            return
        session.answers[key] = value
        await callback.answer()
        if key == "occasion" and value == "birthday":
            session.step = "birthday_years"
            await callback.message.answer(
                "Сколько лет исполняется имениннику? Напишите число, например: 30"
            )
            return
        await _ask_next_card_context(callback.message, callback.from_user.id)
        return

    # --- Сценарий подбора подарка ---
    if session.mode != "gift":
        # Старые кнопки / сбитый режим — вернём в опрос подарка
        session.start_quiz()
        await callback.answer()
        await callback.message.answer(
            "Давайте подберём подарок заново.",
            reply_markup=STEP_KEYBOARDS[session.step](),
        )
        return

    if session.step != key:
        await callback.answer("Сначала ответьте на текущий вопрос.", show_alert=True)
        return

    await callback.answer()

    if key == "occasion" and value == "birthday":
        session.answers[key] = value
        session.step = "birthday_years"
        await callback.message.answer(
            "Сколько лет исполняется имениннику? Напишите число, например: 30"
        )
        return

    next_step = session.set_answer(key, value)

    if next_step is None:
        # Опрос окончен → только идеи подарков, не открытка
        await _fetch_and_show_ideas(callback.message, callback.from_user.id)
        return

    await callback.message.answer(
        STEP_PROMPTS[next_step],
        reply_markup=STEP_KEYBOARDS[next_step](),
    )


@router.message(F.text)
async def free_text(message: Message) -> None:
    session = store.get(message.from_user.id)
    text = (message.text or "").strip()

    if session.step == "birthday_years":
        years = _parse_birthday_years(text)
        if years is None:
            await message.answer(
                "Нужно целое число лет от 1 до 120. Например: 7 или 35. "
                "Попробуйте ещё раз."
            )
            return
        session.answers["birthday_years"] = str(years)

        # В подборе подарка после ДР-возраста идём к бюджету, НЕ к открытке
        if session.mode == "gift" or not session.card_standalone:
            await _continue_gift_quiz_after_birthday(message, message.from_user.id)
            return

        # Только standalone-открытка
        await _ask_next_card_context(message, message.from_user.id)
        return

    if session.step == "card_name":
        if not session.can_generate_card():
            await message.answer(
                "Сначала получите идеи подарков — потом сделаем открытку.",
                reply_markup=main_menu(),
            )
            return
        session.card_answers["card_name"] = text[:60]
        session.step = "card_generating"
        await _run_card_generation(message, message.from_user.id)
        return

    await message.bot.send_chat_action(message.chat.id, action="typing")
    answer = await reply_with_openai(text)
    await message.answer(answer, reply_markup=main_menu())


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Напишите вопрос текстом, нажмите «Подобрать подарок» или «Сделать открытку».",
        reply_markup=main_menu(),
    )
