"""Лимиты генерации открыток (в памяти процесса)."""

from __future__ import annotations

from threading import Lock

from bot.config import get_card_user_limit


def _cards_phrase(count: int) -> str:
    n = abs(count) % 100
    n1 = n % 10
    if 11 <= n <= 14:
        word = "открыток"
    elif n1 == 1:
        word = "открытку"
    elif 2 <= n1 <= 4:
        word = "открытки"
    else:
        word = "открыток"
    return f"{count} {word}"


class CardGuard:
    """
    - Не даёт одному пользователю запустить две генерации сразу.
    - Не больше N успешно созданных открыток на пользователя.

    Хранение только в RAM: после перезапуска бота счётчики обнуляются.
    Неудачная генерация лимит не тратит.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._busy: set[int] = set()
        self._created: dict[int, int] = {}

    def limit_message(self, user_id: int) -> str | None:
        with self._lock:
            return self._limit_message_locked(user_id)

    def begin(self, user_id: int) -> str | None:
        """Возвращает текст ошибки или None, если можно начинать."""
        with self._lock:
            if user_id in self._busy:
                return (
                    "Открытка для вас уже создаётся. "
                    "Подождите окончания текущей генерации."
                )
            blocked = self._limit_message_locked(user_id)
            if blocked:
                return blocked
            self._busy.add(user_id)
            return None

    def commit(self, user_id: int) -> None:
        """Учитывает открытку только после успешной отправки."""
        with self._lock:
            self._created[user_id] = self._created.get(user_id, 0) + 1

    def end(self, user_id: int) -> None:
        with self._lock:
            self._busy.discard(user_id)

    def _limit_message_locked(self, user_id: int) -> str | None:
        limit = get_card_user_limit()
        if limit > 0 and self._created.get(user_id, 0) >= limit:
            return (
                f"На одного пользователя можно создать только {_cards_phrase(limit)}. "
                "Этот лимит уже использован."
            )
        return None


card_guard = CardGuard()
