"""Каталог подарков и логика подбора без платных ИИ-сервисов."""

from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class Gift:
    id: str
    title: str
    price: int
    min_age: int
    max_age: int
    genders: frozenset[str]  # male / female / any
    interests: frozenset[str]
    occasions: frozenset[str]
    recipients: frozenset[str]
    why: str


# Бюджеты: верхняя граница включительно; None = без верхней границы
BUDGET_RANGES: dict[str, tuple[int, int | None]] = {
    "budget_1000": (0, 1000),
    "budget_3000": (1001, 3000),
    "budget_7000": (3001, 7000),
    "budget_more": (7001, None),
}

AGE_RANGES: dict[str, tuple[int, int]] = {
    "age_child": (3, 12),
    "age_teen": (13, 17),
    "age_young": (18, 30),
    "age_adult": (31, 50),
    "age_senior": (51, 90),
}

GIFTS: list[Gift] = [
    Gift(
        "book_set",
        "Набор книг по интересам",
        1200,
        12,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"books", "hobby"}),
        frozenset({"birthday", "ny", "no_reason", "colleague"}),
        frozenset({"mom", "dad", "friend", "girlfriend", "colleague", "partner", "self", "child"}),
        "Универсальный вариант: можно выбрать жанр под увлечения человека.",
    ),
    Gift(
        "thermos",
        "Стильный термос",
        900,
        14,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"sport", "home", "food"}),
        frozenset({"birthday", "ny", "feb23", "colleague", "no_reason"}),
        frozenset({"dad", "friend", "colleague", "partner", "self", "mom"}),
        "Практичный подарок для тех, кто в движении и любит горячие напитки.",
    ),
    Gift(
        "candle_set",
        "Набор ароматических свечей",
        1100,
        16,
        90,
        frozenset({"female", "any"}),
        frozenset({"home", "beauty"}),
        frozenset({"birthday", "ny", "mar8", "valentine", "no_reason", "wedding"}),
        frozenset({"mom", "girlfriend", "partner", "colleague", "self"}),
        "Создаёт уют и подходит почти к любому поводу.",
    ),
    Gift(
        "board_game",
        "Настольная игра для компании",
        1800,
        8,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"hobby", "home"}),
        frozenset({"birthday", "ny", "no_reason", "wedding"}),
        frozenset({"friend", "girlfriend", "partner", "child", "self", "colleague"}),
        "Отличный способ провести вечер вместе — особенно если человек любит игры.",
    ),
    Gift(
        "wireless_earbuds",
        "Беспроводные наушники",
        3500,
        14,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"tech", "sport", "hobby"}),
        frozenset({"birthday", "ny", "feb23", "no_reason"}),
        frozenset({"friend", "girlfriend", "partner", "self", "colleague", "child", "dad", "mom"}),
        "Полезный гаджет для музыки, подкастов и спорта.",
    ),
    Gift(
        "skincare",
        "Набор уходовой косметики",
        2500,
        16,
        90,
        frozenset({"female", "any"}),
        frozenset({"beauty"}),
        frozenset({"birthday", "mar8", "valentine", "ny", "no_reason"}),
        frozenset({"mom", "girlfriend", "partner", "self", "colleague"}),
        "Приятный бьюти-подарок, если человек следит за собой.",
    ),
    Gift(
        "coffee_kit",
        "Набор для кофемана",
        2200,
        18,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"food", "home"}),
        frozenset({"birthday", "ny", "colleague", "no_reason", "feb23"}),
        frozenset({"mom", "dad", "friend", "colleague", "partner", "self"}),
        "Вкусно и по делу: зёрна, кружка или аксессуары под бюджет.",
    ),
    Gift(
        "smart_lamp",
        "Умная лампа / ночник",
        2800,
        10,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"tech", "home"}),
        frozenset({"birthday", "ny", "no_reason", "wedding"}),
        frozenset({"friend", "girlfriend", "partner", "self", "child", "colleague"}),
        "Обновляет атмосферу дома и выглядит современно.",
    ),
    Gift(
        "fitness_band",
        "Фитнес-браслет",
        4500,
        14,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"sport", "tech"}),
        frozenset({"birthday", "ny", "feb23", "mar8", "no_reason"}),
        frozenset({"friend", "girlfriend", "partner", "self", "dad", "mom", "colleague"}),
        "Мотивирует больше двигаться и следить за активностью.",
    ),
    Gift(
        "cooking_class",
        "Мастер-класс по кулинарии",
        4000,
        16,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"food", "hobby"}),
        frozenset({"birthday", "ny", "no_reason", "wedding", "mar8", "valentine"}),
        frozenset({"mom", "dad", "friend", "girlfriend", "partner", "self"}),
        "Подарок-впечатление: запомнится сильнее обычной вещи.",
    ),
    Gift(
        "lego_set",
        "Конструктор / набор для сборки",
        3200,
        5,
        40,
        frozenset({"male", "female", "any"}),
        frozenset({"hobby", "tech"}),
        frozenset({"birthday", "ny", "no_reason"}),
        frozenset({"child", "friend", "self", "partner"}),
        "Развивает внимание и даёт радость от готовой модели.",
    ),
    Gift(
        "plush",
        "Мягкая игрушка-персонаж",
        800,
        3,
        16,
        frozenset({"male", "female", "any"}),
        frozenset({"hobby", "home"}),
        frozenset({"birthday", "ny", "no_reason"}),
        frozenset({"child"}),
        "Тёплый и понятный подарок для ребёнка.",
    ),
    Gift(
        "art_kit",
        "Набор для творчества",
        1500,
        5,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"hobby", "beauty"}),
        frozenset({"birthday", "ny", "mar8", "no_reason"}),
        frozenset({"child", "mom", "girlfriend", "partner", "self", "friend"}),
        "Подходит творческим натурам любого возраста.",
    ),
    Gift(
        "plant_pot",
        "Комнатное растение в красивом кашпо",
        1300,
        16,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"home"}),
        frozenset({"birthday", "ny", "wedding", "colleague", "no_reason", "mar8"}),
        frozenset({"mom", "girlfriend", "partner", "colleague", "self", "friend"}),
        "Оживляет пространство и выглядит заботливо.",
    ),
    Gift(
        "wallet",
        "Качественный кошелёк / картхолдер",
        2700,
        18,
        90,
        frozenset({"male", "any"}),
        frozenset({"home", "hobby"}),
        frozenset({"birthday", "ny", "feb23", "no_reason"}),
        frozenset({"dad", "friend", "partner", "colleague", "self"}),
        "Практичный аксессуар на каждый день.",
    ),
    Gift(
        "jewelry",
        "Изящное украшение",
        5500,
        16,
        90,
        frozenset({"female", "any"}),
        frozenset({"beauty"}),
        frozenset({"birthday", "mar8", "valentine", "wedding", "ny", "no_reason"}),
        frozenset({"mom", "girlfriend", "partner", "self"}),
        "Эмоциональный подарок, если вы знаете вкус человека.",
    ),
    Gift(
        "speaker",
        "Портативная колонка",
        4800,
        12,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"tech", "hobby", "sport"}),
        frozenset({"birthday", "ny", "feb23", "no_reason"}),
        frozenset({"friend", "girlfriend", "partner", "self", "child", "dad", "colleague"}),
        "Музыка везде: дома, на прогулке и в поездках.",
    ),
    Gift(
        "tea_set",
        "Подарочный чайный набор",
        1600,
        18,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"food", "home"}),
        frozenset({"birthday", "ny", "colleague", "no_reason", "mar8", "wedding"}),
        frozenset({"mom", "dad", "colleague", "partner", "friend", "self"}),
        "Уютный и «безопасный» вариант, когда вкусы известны примерно.",
    ),
    Gift(
        "backpack",
        "Городской рюкзак",
        3800,
        12,
        50,
        frozenset({"male", "female", "any"}),
        frozenset({"sport", "hobby", "tech"}),
        frozenset({"birthday", "ny", "no_reason", "feb23"}),
        frozenset({"friend", "girlfriend", "partner", "self", "child", "colleague"}),
        "Удобно для учёбы, работы и коротких поездок.",
    ),
    Gift(
        "massage_gun",
        "Массажёр для мышц",
        6200,
        18,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"sport", "beauty"}),
        frozenset({"birthday", "ny", "feb23", "mar8", "no_reason"}),
        frozenset({"dad", "mom", "friend", "partner", "self", "colleague"}),
        "Забота о восстановлении после тренировок и долгого дня.",
    ),
    Gift(
        "photo_album",
        "Фотоальбом или рамка для фото",
        1000,
        10,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"home", "hobby"}),
        frozenset({"birthday", "ny", "wedding", "valentine", "no_reason", "mar8"}),
        frozenset({"mom", "dad", "partner", "girlfriend", "friend", "self"}),
        "Тёплый личный подарок с воспоминаниями.",
    ),
    Gift(
        "kitchen_gadget",
        "Кухонный гаджет",
        2900,
        18,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"food", "home", "tech"}),
        frozenset({"birthday", "ny", "wedding", "no_reason", "mar8"}),
        frozenset({"mom", "dad", "partner", "self", "friend", "colleague"}),
        "Полезен тем, кто любит готовить и ценит удобство на кухне.",
    ),
    Gift(
        "ticket_cinema",
        "Билеты в кино / на шоу",
        2000,
        10,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"hobby"}),
        frozenset({"birthday", "no_reason", "ny", "wedding", "valentine"}),
        frozenset({"friend", "girlfriend", "partner", "self", "child", "mom", "dad"}),
        "Впечатление вместо вещи — особенно если бюджет средний.",
    ),
    Gift(
        "perfume",
        "Парфюм или набор ароматов",
        7000,
        16,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"beauty"}),
        frozenset({"birthday", "mar8", "valentine", "feb23", "ny", "wedding", "no_reason"}),
        frozenset({"mom", "dad", "girlfriend", "partner", "self", "friend"}),
        "Яркий подарок, если вы уверены в предпочтениях по аромату.",
    ),
    Gift(
        "powerbank",
        "Мощный пауэрбанк",
        1900,
        12,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"tech", "sport"}),
        frozenset({"birthday", "ny", "colleague", "feb23", "no_reason"}),
        frozenset({"friend", "colleague", "partner", "self", "dad", "mom", "child"}),
        "Всегда пригодится владельцу телефона и гаджетов.",
    ),
    Gift(
        "socks_fun",
        "Набор ярких носков",
        700,
        10,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"hobby", "home"}),
        frozenset({"birthday", "ny", "colleague", "no_reason", "feb23"}),
        frozenset({"friend", "colleague", "dad", "partner", "self", "mom"}),
        "Лёгкий и милый подарок, когда нужно уложиться в небольшой бюджет.",
    ),
    Gift(
        "yoga_mat",
        "Коврик для йоги / растяжки",
        2100,
        14,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"sport", "home"}),
        frozenset({"birthday", "ny", "mar8", "no_reason"}),
        frozenset({"mom", "girlfriend", "partner", "self", "friend"}),
        "Поддержит интерес к домашним тренировкам и восстановлению.",
    ),
    Gift(
        "subscription",
        "Подписка на сервис / книгу / музыку",
        1500,
        14,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"books", "tech", "hobby"}),
        frozenset({"birthday", "ny", "no_reason", "colleague"}),
        frozenset({"friend", "girlfriend", "partner", "self", "colleague", "child", "mom", "dad"}),
        "Цифровой подарок без риска «не того размера».",
    ),
    Gift(
        "watch",
        "Стильные часы",
        8500,
        16,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"beauty", "hobby", "tech"}),
        frozenset({"birthday", "ny", "feb23", "mar8", "wedding", "no_reason"}),
        frozenset({"dad", "mom", "partner", "girlfriend", "friend", "self"}),
        "Статусный и заметный подарок для особого случая.",
    ),
    Gift(
        "picnic_set",
        "Набор для пикника",
        3600,
        16,
        90,
        frozenset({"male", "female", "any"}),
        frozenset({"food", "sport", "hobby"}),
        frozenset({"birthday", "ny", "no_reason", "wedding", "valentine"}),
        frozenset({"friend", "girlfriend", "partner", "self", "mom", "dad"}),
        "Для тех, кто любит прогулки, природу и совместные выходные.",
    ),
]


def _age_midpoint(age_key: str) -> int:
    low, high = AGE_RANGES[age_key]
    return (low + high) // 2


def _in_budget(price: int, budget_key: str) -> bool:
    low, high = BUDGET_RANGES[budget_key]
    if price < low:
        return False
    if high is not None and price > high:
        return False
    return True


def _score_gift(gift: Gift, answers: dict[str, str]) -> int:
    score = 0
    age = _age_midpoint(answers["age"])
    if not (gift.min_age <= age <= gift.max_age):
        return -1
    if not _in_budget(gift.price, answers["budget"]):
        return -1

    gender = answers["gender"]
    if gender != "any" and gender not in gift.genders and "any" not in gift.genders:
        return -1

    recipient = answers["recipient"]
    if recipient in gift.recipients:
        score += 3
    elif "self" in gift.recipients or recipient == "self":
        score += 1
    else:
        return -1

    occasion = answers["occasion"]
    if occasion in gift.occasions or "no_reason" in gift.occasions:
        score += 2
    else:
        score -= 1

    interest = answers["interest"]
    if interest in gift.interests:
        score += 4
    else:
        score += 0

    # Чем ближе цена к середине бюджета — тем лучше
    low, high = BUDGET_RANGES[answers["budget"]]
    mid = low if high is None else (low + high) // 2
    score += max(0, 3 - abs(gift.price - mid) // 1500)

    return score


def pick_gifts(
    answers: dict[str, str],
    *,
    count: int = 3,
    exclude_ids: set[str] | None = None,
) -> list[Gift]:
    """Подбирает подарки под ответы. Исключает уже показанные id."""
    exclude_ids = exclude_ids or set()
    ranked: list[tuple[int, Gift]] = []
    for gift in GIFTS:
        if gift.id in exclude_ids:
            continue
        score = _score_gift(gift, answers)
        if score >= 0:
            ranked.append((score, gift))

    ranked.sort(key=lambda item: (-item[0], item[1].title))

    if len(ranked) <= count:
        return [g for _, g in ranked]

    # Берём лучших кандидатов и слегка перемешиваем для разнообразия
    top = ranked[: max(count * 3, count)]
    random.shuffle(top)
    top.sort(key=lambda item: -item[0])
    return [g for _, g in top[:count]]


def format_gift_list(gifts: list[Gift]) -> str:
    if not gifts:
        return (
            "По этим параметрам идей почти не осталось.\n"
            "Попробуйте изменить бюджет или интересы — нажмите «Начать заново»."
        )

    lines = ["Вот идеи подарков под ваши ответы:\n"]
    for i, gift in enumerate(gifts, start=1):
        lines.append(
            f"{i}. {gift.title} — около {gift.price} ₽\n"
            f"   Почему подходит: {gift.why}\n"
        )
    lines.append("Можно взять другие варианты или пройти опрос заново.")
    return "\n".join(lines)
