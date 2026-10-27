"""Клавиатуры с удобными кнопками для телефона."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🎁 Подобрать подарок"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def recipient_kb() -> InlineKeyboardMarkup:
    return _inline(
        [
            ("Маме", "recipient:mom"),
            ("Папе", "recipient:dad"),
            ("Другу", "recipient:friend"),
            ("Подруге", "recipient:girlfriend"),
            ("Партнёру / паре", "recipient:partner"),
            ("Коллеге", "recipient:colleague"),
            ("Ребёнку", "recipient:child"),
            ("Себе", "recipient:self"),
        ]
    )


def gender_kb() -> InlineKeyboardMarkup:
    return _inline(
        [
            ("Мужской", "gender:male"),
            ("Женский", "gender:female"),
            ("Неважно", "gender:any"),
        ]
    )


def age_kb() -> InlineKeyboardMarkup:
    return _inline(
        [
            ("3–12 лет", "age:age_child"),
            ("13–17 лет", "age:age_teen"),
            ("18–30 лет", "age:age_young"),
            ("31–50 лет", "age:age_adult"),
            ("51+", "age:age_senior"),
        ]
    )


def occasion_kb() -> InlineKeyboardMarkup:
    return _inline(
        [
            ("День рождения", "occasion:birthday"),
            ("Новый год", "occasion:ny"),
            ("14 февраля", "occasion:valentine"),
            ("8 Марта", "occasion:mar8"),
            ("23 Февраля", "occasion:feb23"),
            ("Свадьба / годовщина", "occasion:wedding"),
            ("Без повода", "occasion:no_reason"),
            ("Коллеге / офис", "occasion:colleague"),
        ]
    )


def budget_kb() -> InlineKeyboardMarkup:
    return _inline(
        [
            ("До 1 000 ₽", "budget:budget_1000"),
            ("1 000–3 000 ₽", "budget:budget_3000"),
            ("3 000–7 000 ₽", "budget:budget_7000"),
            ("От 7 000 ₽", "budget:budget_more"),
        ]
    )


def interest_kb() -> InlineKeyboardMarkup:
    return _inline(
        [
            ("Книги", "interest:books"),
            ("Техника", "interest:tech"),
            ("Спорт", "interest:sport"),
            ("Красота", "interest:beauty"),
            ("Дом", "interest:home"),
            ("Еда", "interest:food"),
            ("Хобби", "interest:hobby"),
        ]
    )


def results_kb() -> InlineKeyboardMarkup:
    return _inline(
        [
            ("🔄 Другие варианты", "action:more"),
            ("🎁 Начать заново", "action:restart"),
        ],
        row_width=1,
    )


def _inline(
    items: list[tuple[str, str]],
    row_width: int = 2,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for text, data in items:
        builder.add(InlineKeyboardButton(text=text, callback_data=data))
    builder.adjust(row_width)
    return builder.as_markup()


STEP_KEYBOARDS = {
    "recipient": recipient_kb,
    "gender": gender_kb,
    "age": age_kb,
    "occasion": occasion_kb,
    "budget": budget_kb,
    "interest": interest_kb,
}

STEP_PROMPTS = {
    "recipient": "Кому подбираем подарок?",
    "gender": "Укажите пол получателя:",
    "age": "Какой возраст?",
    "occasion": "Какой повод?",
    "budget": "Какой бюджет?",
    "interest": "Что ближе всего по интересам?",
}
