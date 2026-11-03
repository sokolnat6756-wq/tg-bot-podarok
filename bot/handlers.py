"""Обработчики команд и кнопок."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.ai import compose_greeting_wish, reply_with_openai
from bot.gifts import format_gift_list, pick_gifts
from bot.images import generate_greeting_card
from bot.keyboards import (
    STEP_KEYBOARDS,
    STEP_PROMPTS,
    card_offer_kb,
    card_result_kb,
    main_menu,
    results_kb,
)
from bot.limits import card_guard
from bot.session import store

router = Router()

WELCOME = (
    "Привет! Я помогу быстро подобрать идеальный подарок "
    "и при желании сделать персональную поздравительную открытку.\n\n"
    "Нажмите «Подобрать подарок» — ответьте на несколько вопросов. "
    "После выбора пола, возраста и повода предложу создать открытку.\n\n"
    "Можно также сразу нажать «Сделать открытку» или написать вопрос текстом."
)


async def _send_results(message: Message, user_id: int) -> None:
    session = store.get(user_id)
    gifts = pick_gifts(session.answers, count=3, exclude_ids=session.shown_gift_ids)
    for gift in gifts:
        session.shown_gift_ids.add(gift.id)

    if not gifts:
        text = (
            "Новых идей по этим параметрам больше нет.\n"
            "Нажмите «Начать заново» и чуть измените ответы."
        )
    else:
        text = format_gift_list(gifts)

    await message.answer(text, reply_markup=results_kb())


async def _ask_next_card_context(message: Message, user_id: int) -> None:
    session = store.get(user_id)
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
    await message.answer(
        STEP_PROMPTS[missing],
        reply_markup=STEP_KEYBOARDS[missing](),
    )


async def _run_card_generation(message: Message, user_id: int) -> None:
    session = store.get(user_id)
    blocked = card_guard.begin(user_id)
    if blocked:
        await message.answer(blocked, reply_markup=main_menu())
        return

    resume = session.resume_gift_after_card
    try:
        await message.answer(
            "Создаю персональную открытку… Это может занять около минуты. "
            "Пожалуйста, подождите."
        )
        await message.bot.send_chat_action(message.chat.id, action="upload_photo")

        name = session.context_value("card_name") or "Друг"
        occasion = session.context_value("occasion", "no_reason")
        recipient = session.context_value("recipient", "friend")
        age = session.context_value("age", "age_adult")
        gender = session.context_value("gender", "any")

        wish = await compose_greeting_wish(
            name=name,
            occasion_key=occasion,
            recipient_key=recipient,
            age_key=age,
            gender_key=gender,
        )
        session.card_answers["card_wish"] = wish

        result = await generate_greeting_card(
            occasion_key=occasion,
            recipient_key=recipient,
            age_key=age,
            gender_key=gender,
            name=name,
            wish=wish,
        )
        if not result.ok or not result.image_bytes:
            await message.answer(
                result.error or "Не удалось создать открытку.",
                reply_markup=card_result_kb(resume_gift=resume),
            )
            return

        photo = BufferedInputFile(result.image_bytes, filename="greeting_card.png")
        caption = "Ваша персональная открытка готова ✨"
        if resume:
            caption += "\nМожно продолжить подбор подарка."
        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=card_result_kb(resume_gift=resume),
        )
        session.step = "card_done"
    finally:
        card_guard.end(user_id)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    session = store.get(message.from_user.id)
    session.reset()
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(F.text.in_({"🎁 Подобрать подарок", "Подобрать подарок"}))
async def start_quiz(message: Message) -> None:
    session = store.get(message.from_user.id)
    session.start_quiz()
    step = session.step
    await message.answer(
        STEP_PROMPTS[step],
        reply_markup=STEP_KEYBOARDS[step](),
    )


@router.message(F.text.in_({"🖼 Сделать открытку", "Сделать открытку"}))
async def start_card(message: Message) -> None:
    session = store.get(message.from_user.id)
    session.start_card_standalone()
    await _ask_next_card_context(message, message.from_user.id)


@router.callback_query(F.data.startswith("action:"))
async def on_action(callback: CallbackQuery) -> None:
    action = callback.data.split(":", 1)[1]
    session = store.get(callback.from_user.id)
    await callback.answer()

    if action == "restart":
        session.start_quiz()
        step = session.step
        await callback.message.answer(
            STEP_PROMPTS[step],
            reply_markup=STEP_KEYBOARDS[step](),
        )
        return

    if action == "card_yes":
        if session.step != "card_offer" and not session.resume_gift_after_card:
            await callback.message.answer(
                "Сначала пройдите шаги до выбора повода или нажмите «Сделать открытку».",
                reply_markup=main_menu(),
            )
            return
        session.mode = "card"
        session.step = "card_name"
        await callback.message.answer(
            "Как зовут человека, для которого открытка? Напишите имя.",
            reply_markup=main_menu(),
        )
        return

    if action == "card_skip":
        step = session.continue_gift_after_card()
        await callback.message.answer(
            STEP_PROMPTS[step],
            reply_markup=STEP_KEYBOARDS[step](),
        )
        return

    if action == "card_retry":
        if not session.context_value("occasion") or not session.context_value("card_name"):
            await callback.message.answer(
                "Недостаточно данных для повтора. Нажмите «Сделать открытку».",
                reply_markup=main_menu(),
            )
            return
        await _run_card_generation(callback.message, callback.from_user.id)
        return

    if action == "card_again":
        session.start_card_standalone()
        await _ask_next_card_context(callback.message, callback.from_user.id)
        return

    if action == "more":
        if len(session.answers) < 6:
            await callback.message.answer(
                "Сначала пройдите короткий опрос до конца.",
                reply_markup=main_menu(),
            )
            return
        await _send_results(callback.message, callback.from_user.id)
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

    # Сценарий открытки: добираем recipient/gender/age/occasion
    if session.mode == "card" and session.step == key and key in {"recipient", "gender", "age", "occasion"}:
        session.answers[key] = value
        await callback.answer()
        await _ask_next_card_context(callback.message, callback.from_user.id)
        return

    if session.step != key:
        await callback.answer("Сначала ответьте на текущий вопрос.", show_alert=True)
        return

    next_step = session.set_answer(key, value)
    await callback.answer()

    # После пола, возраста и повода — предложение открытки
    if key == "occasion":
        session.pause_for_card_offer()
        await callback.message.answer(
            "Отлично! Могу создать персональную поздравительную открытку "
            "под этот повод. Пожелание я придумаю сам — вам нужно будет "
            "только имя.\n\nСоздать открытку?",
            reply_markup=card_offer_kb(),
        )
        return

    if next_step is None:
        await _send_results(callback.message, callback.from_user.id)
        return

    await callback.message.answer(
        STEP_PROMPTS[next_step],
        reply_markup=STEP_KEYBOARDS[next_step](),
    )


@router.message(F.text)
async def free_text(message: Message) -> None:
    session = store.get(message.from_user.id)
    text = (message.text or "").strip()

    if session.step == "card_name":
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
