"""Callback query handlers for the whole inline navigation."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.catalog import CATEGORIES, get_model
from bot.database.db import Database
from bot.database.models import User
from bot.handlers.commands import HELP_TEXT
from bot.keyboards.inline import (
    admin_menu,
    back_to_menu,
    cancel,
    confirm_reset,
    cost_menu,
    describe_category,
    main_menu,
    models_categories,
    models_list,
    settings_menu,
)
from bot.services.pricing import PricingService, format_cost, format_price_per_million
from bot.services.tokens import format_tokens
from bot.states import ImageStates, SettingsStates
from bot.utils.text import escape_html

logger = logging.getLogger(__name__)

router = Router(name="callbacks")


async def _edit(callback: CallbackQuery, text: str, markup=None) -> None:
    """Safely edit the callback message."""
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.debug("Callback edit failed: %s", exc)


def _main_menu_text(user: User) -> str:
    model = get_model(user.model)
    return (
        f"🏠 <b>Главное меню</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 Модель: <b>{model.name}</b>\n"
        f"📨 Запросов: <b>{user.requests}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выбери действие или просто напиши сообщение ✍️"
    )


def _profile_text(user: User) -> str:
    model = get_model(user.model)
    prompt = escape_html(user.system_prompt) if user.system_prompt else "— (не задан)"
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    return (
        "👤 <b>Профиль</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{user.user_id}</code>\n"
        f"🧠 Модель: <b>{model.name}</b>\n"
        f"🌡 Температура: <b>{user.temperature:.2f}</b>\n"
        f"📝 Промпт: <i>{prompt}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 Запросов: <b>{user.requests}</b>\n"
        f"🔢 Токенов (≈): <b>{format_tokens(user.tokens)}</b>\n"
        f"🪙 Потрачено: <b>{format_cost(user.cost)}</b>\n"
        f"💰 Бюджет: <b>{budget}</b>"
    )


async def _cost_text(user: User, pricing: PricingService) -> str:
    prompt_price, completion_price, image_price = await pricing.get_price(user.model)
    model = get_model(user.model)
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    lines = [
        "🪙 <b>Стоимость и бюджет</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🧠 Модель: <b>{model.name}</b>",
        f"📥 Ввод: <b>{format_price_per_million(prompt_price)}</b> / 1M токенов",
        f"📤 Вывод: <b>{format_price_per_million(completion_price)}</b> / 1M токенов",
    ]
    if model.image_generation:
        lines.append(f"🖼 Изображение: <b>{format_cost(image_price)}</b> / шт")
    lines += [
        "━━━━━━━━━━━━━━━━━━━━",
        f"💸 Потрачено всего: <b>{format_cost(user.cost)}</b>",
        f"💰 Лимит: <b>{budget}</b>",
        "",
        "ℹ️ Цены OpenRouter. При достижении лимита генерация блокируется.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- menu
@router.callback_query(F.data == "menu:main")
async def cb_main(callback: CallbackQuery, user: User, is_admin: bool) -> None:
    await callback.answer()
    await _edit(callback, _main_menu_text(user), main_menu(is_admin))


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery, is_admin: bool) -> None:
    await callback.answer()
    await _edit(callback, HELP_TEXT, main_menu(is_admin))


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, user: User, is_admin: bool) -> None:
    await callback.answer()
    await _edit(callback, _profile_text(user), main_menu(is_admin))


@router.callback_query(F.data == "menu:settings")
async def cb_settings(callback: CallbackQuery, user: User) -> None:
    await callback.answer()
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    text = (
        "🧠 <b>Настройки модели</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🌡 Текущая температура: <b>{user.temperature:.2f}</b>\n"
        f"📝 Промпт: <i>{escape_html(user.system_prompt) if user.system_prompt else '—'}</i>\n"
        f"🪙 Потрачено: <b>{format_cost(user.cost)}</b> (лимит: {budget})"
    )
    await _edit(callback, text, settings_menu())


@router.callback_query(F.data == "menu:models")
async def cb_models(callback: CallbackQuery) -> None:
    await callback.answer()
    await _edit(
        callback,
        "⚙️ <b>Выбор модели</b>\nВыбери категорию:",
        models_categories(),
    )


@router.callback_query(F.data == "menu:context_reset")
async def cb_reset_prompt(callback: CallbackQuery) -> None:
    await callback.answer()
    await _edit(
        callback,
        "🧹 <b>Очистить контекст?</b>\nВся история диалога будет удалена.",
        confirm_reset(),
    )


@router.callback_query(F.data == "menu:image")
async def cb_image(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ImageStates.prompt)
    await _edit(
        callback,
        "🎨 <b>Генерация изображения</b>\n\n"
        "Опишите, что нужно нарисовать, и отправьте сообщение.\n"
        "Для генерации будет использована выбранная модель.",
        cancel(),
    )


@router.callback_query(F.data == "menu:admin")
async def cb_admin(callback: CallbackQuery, is_admin: bool) -> None:
    if not is_admin:
        await callback.answer("⛔️ Недоступно", show_alert=True)
        return
    await callback.answer()
    await _edit(callback, "🛡 <b>Админ-панель</b>", admin_menu())


# ------------------------------------------------------------------- models
@router.callback_query(F.data.startswith("models:cat:"))
async def cb_model_category(callback: CallbackQuery, user: User) -> None:
    category = callback.data.split(":", 2)[2]  # type: ignore[union-attr]
    if category not in {c.key for c in CATEGORIES}:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    await callback.answer()
    await _edit(
        callback,
        f"{describe_category(category)}\nВыбери модель:",
        models_list(category, 0, user.model),
    )


@router.callback_query(F.data.startswith("models:page:"))
async def cb_model_page(callback: CallbackQuery, user: User) -> None:
    _, _, category, page_raw = callback.data.split(":", 3)  # type: ignore[union-attr]
    try:
        page = int(page_raw)
    except ValueError:
        page = 0
    await callback.answer()
    await _edit(
        callback,
        f"{describe_category(category)}\nВыбери модель:",
        models_list(category, page, user.model),
    )


@router.callback_query(F.data.startswith("models:set:"))
async def cb_model_set(
    callback: CallbackQuery, db: Database, user: User, is_admin: bool
) -> None:
    model_id = callback.data.split(":", 2)[2]  # type: ignore[union-attr]
    info = get_model(model_id)
    await db.set_model(user.id, info.id)
    user.model = info.id
    await callback.answer(f"✅ Модель: {info.name}")
    await _edit(callback, _main_menu_text(user), main_menu(is_admin))


# ----------------------------------------------------------------- settings
@router.callback_query(F.data == "settings:temp")
async def cb_settings_temp(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsStates.temperature)
    await _edit(
        callback,
        "🌡 <b>Температура</b>\n\n"
        "Отправьте число от <b>0.0</b> до <b>2.0</b>.\n"
        "Меньше — точнее и суше, больше — креативнее.",
        cancel("menu:settings"),
    )


@router.callback_query(F.data == "settings:prompt")
async def cb_settings_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsStates.system_prompt)
    await _edit(
        callback,
        "📝 <b>Системный промпт</b>\n\n"
        "Отправьте текст, который будет задавать роль и стиль модели.",
        cancel("menu:settings"),
    )


@router.callback_query(F.data == "settings:prompt_reset")
async def cb_prompt_reset(callback: CallbackQuery, db: Database, user: User) -> None:
    await db.set_system_prompt(user.id, None)
    user.system_prompt = None
    await callback.answer("✅ Промпт сброшен")
    await _edit(
        callback,
        "🧠 <b>Настройки модели</b>\nПромпт очищен.",
        settings_menu(),
    )


@router.callback_query(F.data == "settings:cost")
async def cb_cost(callback: CallbackQuery, user: User, pricing: PricingService) -> None:
    await callback.answer()
    await _edit(callback, await _cost_text(user, pricing), cost_menu(user.budget))


@router.callback_query(F.data == "settings:budget")
async def cb_budget(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsStates.budget)
    await _edit(
        callback,
        "💰 <b>Бюджет</b>\n\n"
        "Отправьте сумму в USD (например <code>0.5</code>),\n"
        "или <code>0</code>, чтобы снять лимит.",
        cancel("settings:cost"),
    )


@router.callback_query(F.data == "settings:budget_toggle")
async def cb_budget_toggle(
    callback: CallbackQuery, state: FSMContext, db: Database, user: User, pricing: PricingService
) -> None:
    if user.budget > 0:
        await db.set_budget(user.id, 0.0)
        user.budget = 0.0
        await callback.answer("✅ Лимит отключён")
        await _edit(callback, await _cost_text(user, pricing), cost_menu(user.budget))
        return
    await callback.answer()
    await state.set_state(SettingsStates.budget)
    await _edit(
        callback,
        "💰 <b>Бюджет</b>\n\nВведите сумму в USD, например <code>0.5</code>.",
        cancel("settings:cost"),
    )


@router.callback_query(F.data == "reset:confirm")
async def cb_reset_confirm(callback: CallbackQuery, db: Database, user: User) -> None:
    removed = await db.clear_history(user.id)
    await callback.answer(f"Удалено: {removed}")
    await _edit(
        callback,
        f"🧹 Контекст очищен. Удалено сообщений: <b>{removed}</b>.",
        back_to_menu(),
    )


# --------------------------------------------------------- FSM text handlers
@router.message(SettingsStates.temperature, F.text)
async def set_temperature(message: Message, state: FSMContext, db: Database, user: User) -> None:
    raw = (message.text or "").replace(",", ".").strip()
    try:
        value = float(raw)
    except ValueError:
        await message.answer("⚠️ Введите число, например 0.7")
        return
    if not 0.0 <= value <= 2.0:
        await message.answer("⚠️ Значение должно быть в диапазоне 0.0 – 2.0")
        return
    await db.set_temperature(user.id, value)
    await state.clear()
    await message.answer(
        f"✅ Температура сохранена: <b>{value:.2f}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=settings_menu(),
    )


@router.message(SettingsStates.system_prompt, F.text)
async def set_system_prompt(message: Message, state: FSMContext, db: Database, user: User) -> None:
    prompt = (message.text or "").strip()
    await db.set_system_prompt(user.id, prompt or None)
    await state.clear()
    await message.answer(
        "✅ Системный промпт сохранён.",
        parse_mode=ParseMode.HTML,
        reply_markup=settings_menu(),
    )


@router.message(SettingsStates.budget, F.text)
async def set_budget(
    message: Message, state: FSMContext, db: Database, user: User, pricing: PricingService
) -> None:
    raw = (message.text or "").replace(",", ".").replace("$", "").strip()
    try:
        value = float(raw)
    except ValueError:
        await message.answer("⚠️ Введите сумму в USD, например 0.5 (или 0 для снятия лимита).")
        return
    if value < 0:
        await message.answer("⚠️ Сумма не может быть отрицательной.")
        return
    await db.set_budget(user.id, value)
    user.budget = value
    await state.clear()
    notice = "✅ Лимит снят." if value == 0 else f"✅ Бюджет установлен: {format_cost(value)}"
    await message.answer(notice, parse_mode=ParseMode.HTML)
    await message.answer(await _cost_text(user, pricing), parse_mode=ParseMode.HTML,
                         reply_markup=cost_menu(user.budget))
