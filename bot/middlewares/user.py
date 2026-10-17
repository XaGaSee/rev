"""User resolution middleware (registration + injection)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from bot.config import settings
from bot.database.db import Database


class UserMiddleware(BaseMiddleware):
    """Ensure every interacting user exists and inject the DB record."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        user = await self._db.get_or_create_user(
            user_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            default_model=settings.default_model,
            default_temperature=settings.default_temperature,
        )
        data["user"] = user
        data["is_admin"] = tg_user.id in settings.admin_ids
        return await handler(event, data)
