"""Anti-spam throttling middleware."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """Reject events fired faster than *rate* seconds apart, per user."""

    def __init__(self, rate: float = 0.7) -> None:
        self._rate = rate
        self._last_seen: dict[int, float] = {}

    def _prune(self, now: float) -> None:
        """Drop stale entries so the map cannot grow without bound."""
        if len(self._last_seen) < 10_000:
            return
        stale = [uid for uid, ts in self._last_seen.items() if now - ts > 60.0]
        for uid in stale:
            self._last_seen.pop(uid, None)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        self._prune(now)
        last = self._last_seen.get(user.id, 0.0)

        is_callback = isinstance(event, CallbackQuery)
        threshold = self._rate / 3 if is_callback else self._rate

        if now - last < threshold:
            if is_callback and isinstance(event, CallbackQuery):
                await event.answer("Подождите секунду.", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("Превышен лимит запросов. Повторите позже.")
            return None

        self._last_seen[user.id] = now
        return await handler(event, data)
