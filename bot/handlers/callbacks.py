"""Callback query handlers for the whole inline navigation."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.data.catalog import CATEGORIES, get_model, is_image_model, search_models
from bot.database.db import Database
from bot.database.models import User
from bot.keyboards.inline import (
    admin_menu,
    back_to_main,
    cancel,
    confirm_reset,
    cost_menu,
    describe_category,
    image_models_keyboard,
    main_menu,
    models_list,
    search_results,
    settings_menu,
)
from bot.services.pricing import PricingService, format_cost, format_price_per_million
from bot.states import ImageStates, ModelStates, SettingsStates
from bot.ui import (
    HELP_TEXT,
    get_main_menu_payload,
    get_models_payload,
    get_profile_payload,
)
from bot.utils.text import escape_html

logger = logging.getLogger(__name__)

router = Router(name="callbacks")


async def _edit(callback: CallbackQuery, text: str, markup=None) -> None:
    """Safely edit the callback message."""
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            logger.debug("Callback edit failed: %s", exc)


async def _cost_text(user: User, pricing: PricingService) -> str:
    prompt_price, completion_price, image_price = await pricing.get_price(user.model)
    model = get_model(user.model)
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    lines = [
        "Бюджет и расходы\n",
        f"Модель: {model.label}",
        f"Тариф: {model.price_str}",
        f"Ввод: {format_price_per_million(prompt_price)} / 1M токенов",
        f"Выход: {format_price_per_million(completion_price)} / 1M токенов",
    ]
    if model.supports_image_generation:
        lines.append(f"Изображение: {format_cost(image_price)} / шт")
    lines += [
        "",
        f"Потрачено: {format_cost(user.cost)} · Лимит: {budget}",
        "При достижении лимита генерация приостанавливается.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------- menu
@router.callback_query(F.data == "menu:main")
async def cb_main(
    callback: CallbackQuery, state: FSMContext, db: Database, user: User, is_admin: bool
) -> None:
    await callback.answer()
    await state.clear()
    text, markup = get_main_menu_payload(user, await db.count_messages(user.user_id), is_admin)
    await _edit(callback, text, markup)


@router.callback_query(F.data == "menu:help")
async def cb_help(callback: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
    await callback.answer()
    await state.clear()
    await _edit(callback, HELP_TEXT, main_menu(is_admin))


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, state: FSMContext, user: User, is_admin: bool) -> None:
    await callback.answer()
    await state.clear()
    text, markup = get_profile_payload(user, is_admin)
    await _edit(callback, text, markup)


@router.callback_query(F.data == "menu:settings")
async def cb_settings(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await callback.answer()
    await state.clear()
    model = get_model(user.model)
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    text = (
        "Настройки\n\n"
        f"Модель: {model.label}\n"
        f"Температура: {user.temperature:.2f}\n"
        f"Промпт: {escape_html(user.system_prompt) if user.system_prompt else '—'}\n\n"
        f"Потрачено: {format_cost(user.cost)} · Лимит: {budget}"
    )
    await _edit(callback, text, settings_menu())


@router.callback_query(F.data == "menu:models")
async def cb_models(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    text, markup = get_models_payload()
    await _edit(callback, text, markup)


@router.callback_query(F.data == "menu:context_reset")
async def cb_reset_prompt(callback: CallbackQuery) -> None:
    await callback.answer()
    await _edit(callback, "Очистить контекст диалога?", confirm_reset())


@router.callback_query(F.data == "menu:image")
async def cb_image(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    await callback.answer()
    if not is_image_model(user.model):
        await _edit(
            callback,
            "Текущая модель не генерирует изображения. Выберите модель для рисования:",
            image_models_keyboard(user.model),
        )
        return
    await state.set_state(ImageStates.prompt)
    await _edit(
        callback,
        "Опишите изображение, которое нужно сгенерировать.",
        cancel(),
    )


@router.callback_query(F.data == "menu:admin")
async def cb_admin(callback: CallbackQuery, state: FSMContext, is_admin: bool) -> None:
    if not is_admin:
        await callback.answer("Недоступно", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await _edit(callback, "Админ-панель", admin_menu())


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
        f"{describe_category(category)}\n\nВыберите модель:",
        models_list(category, 0, user.model),
    )


@router.callback_query(F.data.startswith("models:page:"))
async def cb_model_page(callback: CallbackQuery, user: User) -> None:
    _, _, page_raw, category = callback.data.split(":", 3)  # type: ignore[union-attr]
    try:
        page = int(page_raw)
    except ValueError:
        page = 0
    await callback.answer()
    await _edit(
        callback,
        f"{describe_category(category)}\n\nВыберите модель:",
        models_list(category, page, user.model),
    )


@router.callback_query(F.data.startswith("models:set:"))
async def cb_model_set(
    callback: CallbackQuery, state: FSMContext, db: Database, user: User, is_admin: bool
) -> None:
    model_id = callback.data.split(":", 2)[2]  # type: ignore[union-attr]
    info = get_model(model_id)
    await db.set_model(user.user_id, info.id)
    user.model = info.id
    await state.clear()
    if info.supports_image_generation:
        await callback.answer("Модель выбрана. Отправьте описание изображения.")
    else:
        await callback.answer(f"Модель: {info.name}")
    text, markup = get_main_menu_payload(user, await db.count_messages(user.user_id), is_admin)
    await _edit(callback, text, markup)


@router.callback_query(F.data == "models:search")
async def cb_model_search(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ModelStates.WaitForModelSearch)
    await _edit(
        callback,
        "Поиск модели\n\nВведите название или его фрагмент.",
        cancel("menu:models"),
    )


@router.callback_query(F.data.startswith("models:spage:"))
async def cb_model_search_page(callback: CallbackQuery, user: User) -> None:
    _, _, page_raw, query = callback.data.split(":", 3)  # type: ignore[union-attr]
    try:
        page = int(page_raw)
    except ValueError:
        page = 0
    items = search_models(query)
    if not items:
        await callback.answer("Результаты устарели. Выполните поиск заново.", show_alert=True)
        return
    await callback.answer()
    await _edit(
        callback,
        f"Поиск: {escape_html(query)} — найдено {len(items)}",
        search_results(items, page, user.model, query),
    )


@router.message(ModelStates.WaitForModelSearch, F.text)
async def do_model_search(message: Message, state: FSMContext, user: User) -> None:
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Введите минимум 2 символа.")
        return
    items = search_models(query)
    if not items:
        await message.answer(
            f"По запросу «{escape_html(query)}» ничего не найдено.",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel("menu:models"),
        )
        return
    await state.clear()
    await message.answer(
        f"Поиск: {escape_html(query)} — найдено {len(items)}",
        parse_mode=ParseMode.HTML,
        reply_markup=search_results(items, 0, user.model, query),
    )


# ----------------------------------------------------------------- settings
@router.callback_query(F.data == "settings:temp")
async def cb_settings_temp(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsStates.temperature)
    await _edit(
        callback,
        "Температура\n\nВведите значение от 0.0 до 2.0 (например, 0.7).",
        cancel("menu:settings"),
    )


@router.callback_query(F.data == "settings:prompt")
async def cb_settings_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsStates.system_prompt)
    await _edit(
        callback,
        "Системный промпт\n\nВведите текст, который определит роль и стиль модели.",
        cancel("menu:settings"),
    )


@router.callback_query(F.data == "settings:cost")
async def cb_cost(
    callback: CallbackQuery, state: FSMContext, user: User, pricing: PricingService
) -> None:
    await callback.answer()
    await state.clear()
    await _edit(callback, await _cost_text(user, pricing), cost_menu(user.budget))


@router.callback_query(F.data == "settings:budget")
async def cb_budget(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SettingsStates.budget)
    await _edit(
        callback,
        "Бюджет\n\nВведите сумму в USD (например, 0.5) или 0, чтобы снять лимит.",
        cancel("settings:cost"),
    )


@router.callback_query(F.data == "settings:budget_toggle")
async def cb_budget_toggle(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    user: User,
    pricing: PricingService,
) -> None:
    if user.budget > 0:
        await db.set_budget(user.user_id, 0.0)
        user.budget = 0.0
        await callback.answer("Лимит отключён")
        await _edit(callback, await _cost_text(user, pricing), cost_menu(user.budget))
        return
    await callback.answer()
    await state.set_state(SettingsStates.budget)
    await _edit(
        callback,
        "Бюджет\n\nВведите сумму в USD (например, 0.5).",
        cancel("settings:cost"),
    )


@router.callback_query(F.data == "reset:confirm")
async def cb_reset_confirm(callback: CallbackQuery, db: Database, user: User) -> None:
    removed = await db.clear_history(user.user_id)
    await callback.answer("Контекст очищен")
    await _edit(callback, f"Контекст очищен ({removed}).", back_to_main())


# --------------------------------------------------------- FSM text handlers
@router.message(SettingsStates.temperature, F.text)
async def set_temperature(message: Message, state: FSMContext, db: Database, user: User) -> None:
    raw = (message.text or "").replace(",", ".").strip()
    try:
        value = float(raw)
    except ValueError:
        await message.answer("Введите число от 0.0 до 2.0 (например, 0.7).")
        return
    if not 0.0 <= value <= 2.0:
        await message.answer("Допустимый диапазон: 0.0 — 2.0.")
        return
    await db.set_temperature(user.user_id, value)
    await state.clear()
    await message.answer(
        f"Температура сохранена: {value:.2f}",
        reply_markup=settings_menu(),
    )


@router.message(SettingsStates.system_prompt, F.text)
async def set_system_prompt(message: Message, state: FSMContext, db: Database, user: User) -> None:
    prompt = (message.text or "").strip()
    await db.set_system_prompt(user.user_id, prompt or None)
    await state.clear()
    await message.answer("Системный промпт сохранён.", reply_markup=settings_menu())


@router.message(SettingsStates.budget, F.text)
async def set_budget(
    message: Message, state: FSMContext, db: Database, user: User, pricing: PricingService
) -> None:
    raw = (message.text or "").replace(",", ".").replace("$", "").strip()
    try:
        value = float(raw)
    except ValueError:
        await message.answer("Введите сумму в USD (например, 0.5) или 0, чтобы снять лимит.")
        return
    if value < 0:
        await message.answer("Сумма не может быть отрицательной.")
        return
    await db.set_budget(user.user_id, value)
    user.budget = value
    await state.clear()
    await message.answer(
        await _cost_text(user, pricing),
        parse_mode=ParseMode.HTML,
        reply_markup=cost_menu(user.budget),
    )