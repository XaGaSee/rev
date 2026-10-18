"""Single source of truth for shared screens (text + keyboard payloads).

Both the ``/start``-family commands and the callback navigation must render
screens through these builders so the UI can never drift apart.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from bot.config import settings
from bot.data.catalog import get_model
from bot.database.db import utc_today
from bot.database.models import User
from bot.keyboards.inline import main_menu, models_categories
from bot.services.pricing import format_cost
from bot.services.tokens import format_tokens
from bot.utils.text import escape_html

HELP_TEXT = (
    "AI Gateway\n\n"
    "Отправьте сообщение, фото или голосовую заметку — модель вернёт ответ.\n\n"
    "/menu — навигация\n"
    "/model — каталог моделей\n"
    "/profile — профиль и статистика\n"
    "/reset — очистить контекст\n"
    "/help — эта справка"
)


def _plural_messages(count: int) -> str:
    """Russian plural form for the message counter."""
    if count % 10 == 1 and count % 100 != 11:
        return "сообщение"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "сообщения"
    return "сообщений"


def get_main_menu_payload(
    user: User, usage_stats: int, is_admin: bool = False
) -> tuple[str, InlineKeyboardMarkup]:
    """Actual main-screen text and keyboard for *user*.

    ``usage_stats`` is the number of dialog turns currently in context.
    """
    model = get_model(user.model)
    if is_admin:
        limit_line = "без ограничений (администратор)"
    else:
        used = user.daily_count if user.daily_date == utc_today() else 0
        limit_line = f"{used} / {settings.daily_message_limit} запросов (сброс в 00:00 UTC)"
    text = (
        "AI Gateway\n\n"
        f"Модель: {model.label}\n"
        f"Лимит: {limit_line}\n"
        f"Контекст: {usage_stats} {_plural_messages(usage_stats)}\n\n"
        "Отправьте сообщение, фото или голосовую заметку."
    )
    return text, main_menu(is_admin)


def get_models_payload() -> tuple[str, InlineKeyboardMarkup]:
    """Model catalog entry screen."""
    return (
        "Каталог моделей\n\nВыберите категорию или выполните поиск по названию.",
        models_categories(),
    )


def get_profile_payload(user: User, is_admin: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    """Profile screen with the token/cost breakdown."""
    model = get_model(user.model)
    prompt = escape_html(user.system_prompt) if user.system_prompt else "—"
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    text = (
        "Профиль\n\n"
        f"ID: {user.user_id}\n"
        f"Модель: {model.label}\n"
        f"Температура: {user.temperature:.2f}\n"
        f"Промпт: {prompt}\n\n"
        f"Запросов: {user.requests}\n"
        f"Токены: вход {format_tokens(user.prompt_tokens)} / "
        f"выход {format_tokens(user.completion_tokens)}\n"
        f"Потрачено: {format_cost(user.cost)} · Бюджет: {budget}"
    )
    return text, main_menu(is_admin)