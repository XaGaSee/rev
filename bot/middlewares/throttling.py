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
        last = self._last_seen.get(user.id, 0.0)

        is_callback = isinstance(event, CallbackQuery)
        threshold = self._rate / 3 if is_callback else self._rate

        if now - last < threshold:
            if is_callback and isinstance(event, CallbackQuery):
                await event.answer("⏳ Слишком быстро, подождите секунду…", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("⏳ Слишком много запросов. Немного подождите.")
            return None

        self._last_seen[user.id] = now
        return await handler(event, data)
