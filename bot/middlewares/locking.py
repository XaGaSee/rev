"""Per-user concurrency guard preventing overlapping generations."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject


class ConcurrencyGuard:
    """Tracks which users currently have an in-flight generation."""

    def __init__(self) -> None:
        self._active: set[int] = set()

    def acquire(self, user_id: int) -> bool:
        """Reserve the slot. Returns ``False`` if a request is already running."""
        if user_id in self._active:
            return False
        self._active.add(user_id)
        return True

    def release(self, user_id: int) -> None:
        """Free the slot."""
        self._active.discard(user_id)

    def is_busy(self, user_id: int) -> bool:
        return user_id in self._active


class ConcurrencyMiddleware(BaseMiddleware):
    """Reject a new message while the same user's previous request is running.

    Command messages (starting with ``/``) are always allowed so users can
    still reset context or open the menu during a long generation.
    """

    def __init__(self, guard: ConcurrencyGuard, notice: str | None = None) -> None:
        self._guard = guard
        self._notice = notice or "Дождитесь завершения текущего запроса."

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        text = event.text or event.caption or ""
        if text.startswith("/"):
            return await handler(event, data)

        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        if not self._guard.acquire(user.id):
            await event.answer(self._notice)
            return None

        try:
            return await handler(event, data)
        finally:
            self._guard.release(user.id)
