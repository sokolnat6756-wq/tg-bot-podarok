"""Автопроверка критериев из BRIEF, раздел 8 (без Telegram и токена)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.gifts import AGE_RANGES, BUDGET_RANGES, pick_gifts
from bot.session import store


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_budget_and_age() -> None:
    answers = {
        "recipient": "mom",
        "gender": "female",
        "age": "age_adult",
        "occasion": "birthday",
        "budget": "budget_3000",
        "interest": "home",
    }
    gifts = pick_gifts(answers, count=3)
    _assert(len(gifts) > 0, "Должен найтись хотя бы один подарок")
    low, high = BUDGET_RANGES[answers["budget"]]
    age_low, age_high = AGE_RANGES[answers["age"]]
    mid_age = (age_low + age_high) // 2
    for g in gifts:
        _assert(g.price >= low, f"{g.title}: цена ниже бюджета")
        if high is not None:
            _assert(g.price <= high, f"{g.title}: цена выше бюджета")
        _assert(g.min_age <= mid_age <= g.max_age, f"{g.title}: возраст не подходит")


def test_no_repeats() -> None:
    answers = {
        "recipient": "friend",
        "gender": "any",
        "age": "age_young",
        "occasion": "ny",
        "budget": "budget_7000",
        "interest": "tech",
    }
    shown: set[str] = set()
    first = pick_gifts(answers, count=3, exclude_ids=shown)
    shown.update(g.id for g in first)
    second = pick_gifts(answers, count=3, exclude_ids=shown)
    overlap = shown.intersection(g.id for g in second)
    _assert(not overlap, f"Повтор идей: {overlap}")


def test_users_isolated() -> None:
    a = store.get(111)
    b = store.get(222)
    a.start_quiz()
    b.start_quiz()
    a.set_answer("recipient", "mom")
    _assert(b.answers.get("recipient") is None, "Ответ пользователя A попал к B")
    _assert(a.answers["recipient"] == "mom", "Ответ пользователя A не сохранился")
    b.set_answer("recipient", "dad")
    _assert(a.answers["recipient"] == "mom", "Ответ B перезаписал сессию A")
    _assert(b.answers["recipient"] == "dad", "Ответ B не сохранился")


def main() -> None:
    test_budget_and_age()
    test_no_repeats()
    test_users_isolated()
    print("OK: бюджет/возраст, без повторов, изоляция пользователей — пройдено.")


if __name__ == "__main__":
    main()
