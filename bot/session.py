"""Изолированные сессии пользователей (в памяти процесса)."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


STEPS = (
    "recipient",
    "gender",
    "age",
    "occasion",
    "budget",
    "interest",
)

# Для отдельной кнопки «Сделать открытку», если данных ещё нет
CARD_CONTEXT_STEPS = (
    "recipient",
    "gender",
    "age",
    "occasion",
)


@dataclass
class UserSession:
    step: str | None = None
    mode: str | None = None  # "gift" | "card"
    answers: dict[str, str] = field(default_factory=dict)
    card_answers: dict[str, str] = field(default_factory=dict)
    shown_gift_ids: set[str] = field(default_factory=set)
    resume_gift_after_card: bool = False

    def reset(self) -> None:
        self.step = None
        self.mode = None
        self.answers.clear()
        self.card_answers.clear()
        self.shown_gift_ids.clear()
        self.resume_gift_after_card = False

    def start_quiz(self) -> None:
        self.mode = "gift"
        self.answers.clear()
        self.card_answers.clear()
        self.shown_gift_ids.clear()
        self.resume_gift_after_card = False
        self.step = STEPS[0]

    def start_card_standalone(self) -> None:
        """Отдельный сценарий открытки: добираем недостающий контекст."""
        self.mode = "card"
        self.resume_gift_after_card = False
        self.card_answers.clear()
        missing = self.next_missing_card_context()
        self.step = missing or "card_name"

    def set_answer(self, key: str, value: str) -> str | None:
        """Сохраняет ответ и возвращает следующий шаг или None, если опрос закончен."""
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

    def pause_for_card_offer(self) -> None:
        self.step = "card_offer"
        self.resume_gift_after_card = True

    def continue_gift_after_card(self) -> str:
        self.mode = "gift"
        self.step = "budget"
        self.resume_gift_after_card = False
        return self.step

    def next_missing_card_context(self) -> str | None:
        for key in CARD_CONTEXT_STEPS:
            if key not in self.answers:
                return key
        if not (self.card_answers.get("card_name") or "").strip():
            return "card_name"
        return None

    def context_value(self, key: str, default: str = "") -> str:
        if key == "card_name":
            return (self.card_answers.get("card_name") or "").strip()
        return self.answers.get(key) or self.card_answers.get(key) or default


class SessionStore:
    """Хранилище сессий: у каждого user_id своё состояние."""

    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}
        self._lock = Lock()

    def get(self, user_id: int) -> UserSession:
        with self._lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = UserSession()
            return self._sessions[user_id]


store = SessionStore()
