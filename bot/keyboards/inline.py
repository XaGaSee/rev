"""Inline keyboard builders."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.catalog import CATEGORIES, models_by_category

PAGE_SIZE = 6


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Primary navigation menu."""
    rows: list[list[InlineKeyboardButton]] = [
        [_btn("⚙️ Выбор модели", "menu:models"), _btn("🧠 Настройки", "menu:settings")],
        [_btn("👤 Профиль", "menu:profile"), _btn("🧹 Сбросить контекст", "menu:context_reset")],
        [_btn("🎨 Генерация изображения", "menu:image")],
        [_btn("❓ Помощь", "menu:help")],
    ]
    if is_admin:
        rows.append([_btn("🛡 Админ-панель", "menu:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu() -> InlineKeyboardMarkup:
    """Single button returning to the main menu."""
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ В меню", "menu:main")]])


def models_categories() -> InlineKeyboardMarkup:
    """Category picker for the model catalog."""
    rows = [[_btn(f"{c.icon} {c.title}", f"models:cat:{c.key}")] for c in CATEGORIES]
    rows.append([_btn("⬅️ В меню", "menu:main")])
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
        mark = "✅ " if model.id == current_model else ""
        rows.append([_btn(f"{mark}{model.label}", f"models:set:{model.id}")])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(_btn("⬅️", f"models:page:{category}:{page - 1}"))
    nav.append(_btn(f"{page + 1}/{total_pages}", f"models:page:{category}:{page}"))
    if page < total_pages - 1:
        nav.append(_btn("➡️", f"models:page:{category}:{page + 1}"))
    rows.append(nav)
    rows.append([_btn("🗂 Категории", "menu:models"), _btn("⬅️ В меню", "menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_menu() -> InlineKeyboardMarkup:
    """Settings for the active model."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🌡 Температура", "settings:temp")],
            [_btn("📝 Системный промпт", "settings:prompt")],
            [_btn("🪙 Стоимость и бюджет", "settings:cost")],
            [_btn("🔄 Сбросить промпт", "settings:prompt_reset")],
            [_btn("⬅️ В меню", "menu:main")],
        ]
    )


def cost_menu(budget: float) -> InlineKeyboardMarkup:
    """Cost / budget management buttons."""
    toggle = "🚫 Отключить лимит" if budget > 0 else "💰 Задать бюджет"
    extra = [_btn("✏️ Изменить бюджет", "settings:budget")] if budget > 0 else []
    rows = [[_btn(toggle, "settings:budget_toggle")]]
    if extra:
        rows.append(extra)
    rows.append([_btn("⬅️ Назад", "menu:settings"), _btn("🏠 В меню", "menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel(menu_cb: str = "menu:main") -> InlineKeyboardMarkup:
    """Cancel button for FSM input flows."""
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("✖️ Отмена", menu_cb)]])


def confirm_reset() -> InlineKeyboardMarkup:
    """Confirmation for clearing the dialog context."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("✅ Да, очистить", "reset:confirm"), _btn("✖️ Отмена", "menu:main")]
        ]
    )


def image_actions(model_id: str) -> InlineKeyboardMarkup:
    """Actions shown when a generated image is produced."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("🔁 Ещё раз", "menu:image")],
            [
                _btn("⚙️ Модель", "menu:models"),
                _btn("⬅️ В меню", "menu:main"),
            ],
        ]
    )


def admin_menu() -> InlineKeyboardMarkup:
    """Admin panel buttons."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("📊 Статистика", "admin:stats")],
            [_btn("📢 Рассылка", "admin:broadcast")],
            [_btn("⬅️ В меню", "menu:main")],
        ]
    )


def describe_category(category_key: str) -> str:
    """Human description for a category (used in headers)."""
    for category in CATEGORIES:
        if category.key == category_key:
            return f"{category.icon} <b>{category.title}</b>"
    return "🗂 <b>Модели</b>"
