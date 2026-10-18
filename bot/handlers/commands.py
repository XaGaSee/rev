"""Command handlers: /start, /help, /menu, /profile, /reset."""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.config import settings
from bot.catalog import get_model
from bot.database.db import Database
from bot.database.models import User
from bot.keyboards.inline import main_menu
from bot.services.pricing import format_cost
from bot.services.tokens import format_tokens

router = Router(name="commands")

HELP_TEXT = (
    "Просто напишите сообщение — бот ответит.\n\n"
    "🖼 Фото — анализ изображения (нужна vision-модель)\n"
    "🎙 Голосовое — распознаётся и отправляется модели\n"
    "🎨 Нарисовать — генерация изображения\n\n"
    "/menu — меню · /model — модели · /profile — профиль\n"
    "/reset — очистить контекст · /help — справка"
)


async def send_main_menu(message: Message, user: User, is_admin: bool) -> None:
    """Send the main menu with a short status header."""
    model = get_model(user.model)
    used = user.daily_count if user.daily_date == datetime.now(timezone.utc).date().isoformat() else 0
    text = (
        f"Модель: <b>{model.name}</b> · {model.price_str}\n"
        f"Лимит: {used}/{settings.daily_message_limit} · Запросов: {user.requests}"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu(is_admin))


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, is_admin: bool) -> None:
    await send_main_menu(message, user, is_admin)


@router.message(Command("menu"))
async def cmd_menu(message: Message, user: User, is_admin: bool) -> None:
    await send_main_menu(message, user, is_admin)


@router.message(Command("help"))
async def cmd_help(message: Message, is_admin: bool) -> None:
    await message.answer(HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=main_menu(is_admin))


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User, is_admin: bool) -> None:
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
        f"🪙 Потрачено: <b>{format_cost(user.cost)}</b> · Бюджет: {budget}\n"
        f"📅 С {user.created_at[:10]}"
    )
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu(is_admin))


@router.message(Command("model"))
async def cmd_model(message: Message, user: User) -> None:
    from bot.keyboards.inline import models_categories

    await message.answer(
        "⚙️ <b>Выбор модели</b>\nВыбери категорию:",
        parse_mode=ParseMode.HTML,
        reply_markup=models_categories(),
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, db: Database, user: User, is_admin: bool) -> None:
    removed = await db.clear_history(user.id)
    await message.answer(
        f"Контекст очищен ({removed} сообщений).",
        reply_markup=main_menu(is_admin),
    )
