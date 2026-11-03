"""Изолированные сессии пользователей (в памяти процесса)."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


# Порядок опроса подарка: повод и возраст ДР до бюджета/интересов
STEPS = (
    "recipient",
    "gender",
    "age",
    "occasion",
    "budget",
    "interest",
)


@dataclass
class UserSession:
    step: str | None = None
    # gift — подбор подарка; card — только если пользователь явно выбрал открытку после подарка
    # или отдельную кнопку «Сделать открытку»
    mode: str | None = None
    card_standalone: bool = False
    answers: dict[str, str] = field(default_factory=dict)
    card_answers: dict[str, str] = field(default_factory=dict)
    last_ideas: list[dict[str, str]] = field(default_factory=list)
    shown_titles: list[str] = field(default_factory=list)
    selected_gift: dict[str, str] | None = None  # на будущее (где купить и т.п.), сейчас не обязателен
    ready_for_card: bool = False
    waiting_message_id: int | None = None

    def reset(self) -> None:
        self.step = None
        self.mode = None
        self.card_standalone = False
        self.answers.clear()
        self.card_answers.clear()
        self.last_ideas.clear()
        self.shown_titles.clear()
        self.selected_gift = None
        self.ready_for_card = False
        self.waiting_message_id = None

    def start_quiz(self) -> None:
        """Строго сценарий подарка. Открытка здесь не запускается."""
        self.reset()
        self.mode = "gift"
        self.card_standalone = False
        self.step = STEPS[0]

    def start_card_standalone(self) -> None:
        """Отдельная кнопка «Сделать открытку» — без подбора подарка."""
        self.mode = "card"
        self.card_standalone = True
        self.card_answers.clear()
        self.selected_gift = None
        self.ready_for_card = True
        self.step = self.next_missing_card_context() or "card_name"

    def set_answer(self, key: str, value: str) -> str | None:
        self.answers[key] = value
        try:
            idx = STEPS.index(key)
        except ValueError:
            return None
        if idx + 1 < len(STEPS):
            self.step = STEPS[idx + 1]
            return self.step
        self.step = "results"
        return None

    def quiz_complete(self) -> bool:
        required = {"recipient", "gender", "age", "occasion", "budget", "interest"}
        if not required.issubset(self.answers):
            return False
        if self.answers.get("occasion") == "birthday" and not (
            self.answers.get("birthday_years") or ""
        ).strip():
            return False
        return True

    def next_missing_card_context(self) -> str | None:
        for key in ("recipient", "gender", "age", "occasion"):
            if key not in self.answers:
                return key
        if self.answers.get("occasion") == "birthday" and not (
            self.answers.get("birthday_years") or ""
        ).strip():
            return "birthday_years"
        if not (self.card_answers.get("card_name") or "").strip():
            return "card_name"
        return None

    def can_generate_card(self) -> bool:
        """Открытка после показа идей или в отдельном сценарии открытки."""
        if self.card_standalone:
            return True
        return self.ready_for_card

    def context_value(self, key: str, default: str = "") -> str:
        if key == "card_name":
            return (self.card_answers.get("card_name") or "").strip()
        return self.answers.get(key) or self.card_answers.get(key) or default

    def remember_ideas(self, ideas: list[dict[str, str]]) -> None:
        self.last_ideas = ideas
        self.ready_for_card = True
        for idea in ideas:
            title = (idea.get("title") or "").strip()
            if title and title not in self.shown_titles:
                self.shown_titles.append(title)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}
        self._lock = Lock()

    def get(self, user_id: int) -> UserSession:
        with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = UserSession()
            return self._sessions[user_id]


store = SessionStore()
