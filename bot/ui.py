"""Single source of truth for shared screens (text + keyboard payloads).

Both the ``/start``-family commands and the callback navigation must render
screens through these builders so the UI can never drift apart.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from bot.catalog import get_model
from bot.config import settings
from bot.database.db import utc_today
from bot.database.models import User
from bot.keyboards.inline import main_menu, models_categories
from bot.services.pricing import format_cost
from bot.services.tokens import format_tokens

HELP_TEXT = (
    "Просто напишите сообщение — бот ответит.\n\n"
    "🖼 Фото — анализ изображения (нужна vision-модель)\n"
    "🎙 Голосовое — распознаётся и отправляется модели\n"
    "🎨 Нарисовать — генерация изображения\n\n"
    "/menu — меню · /model — модели · /profile — профиль\n"
    "/reset — очистить контекст · /help — справка"
)


def get_main_menu_payload(user: User, is_admin: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """Actual main-screen text and keyboard for *user*."""
    model = get_model(user.model)
    if user.user_id in settings.admin_ids:
        limit_line = "без лимита (админ)"
    else:
        used = user.daily_count if user.daily_date == utc_today() else 0
        limit_line = f"{used}/{settings.daily_message_limit}"
    text = (
        f"Модель: <b>{model.name}</b> · {model.price_str}\n"
        f"Лимит: {limit_line} · Запросов: {user.requests}\n"
        "Напишите сообщение или выберите действие."
    )
    return text, main_menu(is_admin)


def get_models_payload() -> tuple[str, InlineKeyboardMarkup]:
    """Model catalog entry screen."""
    return "Модели\nВыберите категорию или воспользуйтесь поиском.", models_categories()


def get_profile_payload(user: User, is_admin: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """Profile screen with the token/cost breakdown."""
    model = get_model(user.model)
    prompt = user.system_prompt or "—"
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    text = (
        f"🆔 <code>{user.user_id}</code>\n"
        f"🧠 Модель: <b>{model.name}</b> · {model.price_str}\n"
        f"🌡 Температура: {user.temperature:.2f}\n"
        f"📝 Промпт: <i>{prompt}</i>\n"
        f"📨 Запросов: {user.requests}\n"
        f"🔢 Токены: вход {format_tokens(user.prompt_tokens)} / "
        f"выход {format_tokens(user.completion_tokens)}\n"
        f"🪙 Потрачено: <b>{format_cost(user.cost)}</b> · Бюджет: {budget}"
    )
    return text, main_menu(is_admin)