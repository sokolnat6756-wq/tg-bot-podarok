"""Обработчики команд и кнопок."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.gifts import format_gift_list, pick_gifts
from bot.keyboards import (
    STEP_KEYBOARDS,
    STEP_PROMPTS,
    main_menu,
    results_kb,
)
from bot.session import store

router = Router()

WELCOME = (
    "Привет! Я помогу быстро подобрать идеальный подарок.\n\n"
    "Ответьте на несколько коротких вопросов — и я предложу 3 идеи "
    "с пояснениями, в рамках вашего бюджета.\n\n"
    "Нажмите «Подобрать подарок», чтобы начать."
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


@router.callback_query(F.data.startswith("action:"))
async def on_action(callback: CallbackQuery) -> None:
    action = callback.data.split(":", 1)[1]
    session = store.get(callback.from_user.id)

    if action == "restart":
        session.start_quiz()
        step = session.step
        await callback.message.answer(
            STEP_PROMPTS[step],
            reply_markup=STEP_KEYBOARDS[step](),
        )
        await callback.answer()
        return

    if action == "more":
        if len(session.answers) < 6:
            await callback.answer("Сначала пройдите короткий опрос.", show_alert=True)
            return
        await _send_results(callback.message, callback.from_user.id)
        await callback.answer()
        return

    await callback.answer()


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

    if session.step != key:
        await callback.answer("Сначала ответьте на текущий вопрос.", show_alert=True)
        return

    next_step = session.set_answer(key, value)
    await callback.answer()

    if next_step is None:
        await _send_results(callback.message, callback.from_user.id)
        return

    await callback.message.answer(
        STEP_PROMPTS[next_step],
        reply_markup=STEP_KEYBOARDS[next_step](),
    )


@router.message()
async def fallback(message: Message) -> None:
    await message.answer(
        "Нажмите «Подобрать подарок» или отправьте /start.",
        reply_markup=main_menu(),
    )
