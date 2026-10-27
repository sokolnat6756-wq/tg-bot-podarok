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


@dataclass
class UserSession:
    step: str | None = None
    answers: dict[str, str] = field(default_factory=dict)
    shown_gift_ids: set[str] = field(default_factory=set)

    def reset(self) -> None:
        self.step = None
        self.answers.clear()
        self.shown_gift_ids.clear()

    def start_quiz(self) -> None:
        self.answers.clear()
        self.shown_gift_ids.clear()
        self.step = STEPS[0]

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
