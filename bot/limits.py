"""Лимиты генерации открыток (в памяти процесса)."""

from __future__ import annotations

import time
from threading import Lock

from bot.config import get_card_hourly_limit


class CardGuard:
    """
    - Не даёт одному пользователю запустить две генерации сразу.
    - Считает число успешных/запущенных запросов за скользящий час.

    Хранение только в RAM: после перезапуска бота счётчики обнуляются.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._busy: set[int] = set()
        self._started_at: dict[int, list[float]] = {}

    def begin(self, user_id: int) -> str | None:
        """Возвращает текст ошибки или None, если можно начинать."""
        limit = get_card_hourly_limit()
        now = time.time()
        with self._lock:
            if user_id in self._busy:
                return (
                    "Открытка для вас уже создаётся. "
                    "Подождите окончания текущей генерации."
                )
            stamps = [t for t in self._started_at.get(user_id, []) if now - t < 3600]
            self._started_at[user_id] = stamps
            if limit > 0 and len(stamps) >= limit:
                return (
                    f"Достигнут лимит: не больше {limit} открыток в час. "
                    "Попробуйте позже или продолжите подбор подарка."
                )
            self._busy.add(user_id)
            stamps.append(now)
            self._started_at[user_id] = stamps
            return None

    def end(self, user_id: int) -> None:
        with self._lock:
            self._busy.discard(user_id)


card_guard = CardGuard()
