"""Inline keyboard builders — compact, no decorative symbols."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.catalog import CATEGORIES, ModelInfo, image_models, models_by_category, vision_models

PAGE_SIZE = 6


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Primary navigation menu."""
    rows: list[list[InlineKeyboardButton]] = [
        [_btn("Модели", "menu:models"), _btn("Поиск", "models:search")],
        [_btn("Настройки", "menu:settings"), _btn("Профиль", "menu:profile")],
        [_btn("Нарисовать", "menu:image"), _btn("Очистить диалог", "menu:context_reset")],
        [_btn("Помощь", "menu:help")],
    ]
    if is_admin:
        rows.append([_btn("Админ-панель", "menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu() -> InlineKeyboardMarkup:
    """Single button returning to the main menu."""
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Меню", "menu:main")]])


def models_categories() -> InlineKeyboardMarkup:
    """Category picker for the model catalog."""
    rows = [[_btn(c.title, f"models:cat:{c.key}")] for c in CATEGORIES]
    rows.append([_btn("Поиск", "models:search"), _btn("Меню", "menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def models_list(category: str, page: int, current_model: str) -> InlineKeyboardMarkup:
    """Paginated list of models for *category*."""
    items = models_by_category(category)
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]

    rows: list[list[InlineKeyboardButton]] = []
    for model in chunk:
        mark = "• " if model.id == current_model else ""
        rows.append([_btn(f"{mark}{model.catalog_label}", f"models:set:{model.id}")])

    if total_pages > 1:
        rows.append(_nav_row("models:page", category, page, total_pages))
    rows.append([_btn("Поиск", "models:search"), _btn("Категории", "menu:models")])
    rows.append([_btn("Меню", "menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_results(
    items: list[ModelInfo], page: int, current_model: str, query: str = ""
) -> InlineKeyboardMarkup:
    """Paginated results of a model search (query travels in callback data)."""
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = items[start : start + PAGE_SIZE]

    rows: list[list[InlineKeyboardButton]] = []
    for model in chunk:
        mark = "• " if model.id == current_model else ""
        rows.append([_btn(f"{mark}{model.catalog_label}", f"models:set:{model.id}")])

    if total_pages > 1:
        rows.append(_nav_row("models:spage", query[:20], page, total_pages))
    rows.append([_btn("Новый поиск", "models:search"), _btn("Категории", "menu:models")])
    rows.append([_btn("Меню", "menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _nav_row(prefix: str, payload: str, page: int, total_pages: int) -> list[InlineKeyboardButton]:
    """Compact pagination row: ← page/total →."""
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(_btn("←", f"{prefix}:{page - 1}:{payload}"))
    row.append(_btn(f"{page + 1}/{total_pages}", f"{prefix}:{page}:{payload}"))
    if page < total_pages - 1:
        row.append(_btn("→", f"{prefix}:{page + 1}:{payload}"))
    return row


def image_models_keyboard(current_model: str = "") -> InlineKeyboardMarkup:
    """One-click switch to an image generation model."""
    return _switch_keyboard(image_models(), current_model)


def vision_models_keyboard(current_model: str = "") -> InlineKeyboardMarkup:
    """One-click switch to a vision-capable model."""
    return _switch_keyboard(vision_models(), current_model)


def _switch_keyboard(items: list[ModelInfo], current_model: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for model in items:
        mark = "• " if model.id == current_model else ""
        rows.append([_btn(f"{mark}{model.catalog_label}", f"models:set:{model.id}")])
    rows.append([_btn("Все модели", "menu:models"), _btn("Меню", "menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_menu() -> InlineKeyboardMarkup:
    """Settings for the active model."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Температура", "settings:temp"), _btn("Системный промпт", "settings:prompt")],
            [_btn("Бюджет", "settings:cost")],
            [_btn("Меню", "menu:main")],
        ]
    )


def cost_menu(budget: float) -> InlineKeyboardMarkup:
    """Cost / budget management buttons."""
    rows = [[_btn("Задать бюджет" if budget <= 0 else "Изменить бюджет", "settings:budget")]]
    if budget > 0:
        rows.append([_btn("Отключить лимит", "settings:budget_toggle")])
    rows.append([_btn("Назад", "menu:settings"), _btn("Меню", "menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel(menu_cb: str = "menu:main") -> InlineKeyboardMarkup:
    """Cancel button for FSM input flows."""
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("Отмена", menu_cb)]])


def confirm_reset() -> InlineKeyboardMarkup:
    """Confirmation for clearing the dialog context."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("Да", "reset:confirm"), _btn("Отмена", "menu:main")]]
    )


def image_actions() -> InlineKeyboardMarkup:
    """Actions shown when a generated image is produced."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Ещё раз", "menu:image"), _btn("Модели", "menu:models")],
            [_btn("Меню", "menu:main")],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    """Admin panel buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Статистика", "admin:stats"), _btn("Обновить прайс", "admin:pricing")],
            [_btn("Рассылка", "admin:broadcast")],
            [_btn("Меню", "menu:main")],
        ]
    )


def describe_category(category_key: str) -> str:
    """Human description for a category (used in headers)."""
    for category in CATEGORIES:
        if category.key == category_key:
            return f"<b>{category.title}</b>"
    return "<b>Модели</b>"