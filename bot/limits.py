"""Лимиты генерации открыток. Счётчик сохраняется на диск."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock

from bot.config import get_card_user_limit

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STORE_PATH = _DATA_DIR / "card_limits.json"


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
    - Счётчик пишется в data/card_limits.json и переживает перезапуск.
    - Неудачная генерация лимит не тратит.
    """

    def __init__(self, store_path: Path = _STORE_PATH) -> None:
        self._lock = Lock()
        self._busy: set[int] = set()
        self._store_path = store_path
        self._created = self._load()

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
            self._save_locked()

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

    def _load(self) -> dict[int, int]:
        if not self._store_path.is_file():
            return {}
        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Не удалось прочитать %s", self._store_path)
            return {}
        if not isinstance(raw, dict):
            return {}
        created: dict[int, int] = {}
        for key, value in raw.items():
            try:
                user_id = int(key)
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count > 0:
                created[user_id] = count
        return created

    def _save_locked(self) -> None:
        payload = {str(user_id): count for user_id, count in sorted(self._created.items())}
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._store_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tmp.replace(self._store_path)
        except OSError:
            logger.exception("Не удалось сохранить %s", self._store_path)


card_guard = CardGuard()
