"""Command handlers: /start, /help, /menu, /profile, /reset."""

from __future__ import annotations

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
    "🤖 <b>Помощь</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "Просто отправь текст — и получишь ответ модели.\n\n"
    "🖼 <b>Изображения:</b> отправь фото (с подписью или без) — "
    "модель проанализирует его.\n"
    "🎙 <b>Голос:</b> отправь голосовое — бот расшифрует его и ответит.\n"
    "🎨 <b>Генерация картинок:</b> выбери модель из категории "
    "«Генерация графики» или нажми кнопку в меню.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "⚙️ <b>Управление</b>\n"
    "• /menu — главное меню\n"
    "• /model — выбрать модель\n"
    "• /profile — профиль и статистика\n"
    "• /reset — очистить контекст диалога\n"
    "• /help — эта справка"
)


async def send_main_menu(message: Message, user: User, is_admin: bool) -> None:
    """Send the main menu with a short status header."""
    model = get_model(user.model)
    text = (
        f"👋 <b>Привет, {user.display_name}!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 Модель: <b>{model.name}</b> · {model.price_str}\n"
        f"🌡 Температура: <b>{user.temperature:.2f}</b>\n"
        f"📨 Запросов: <b>{user.requests}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выбери действие или просто напиши сообщение ✍️"
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
    prompt = user.system_prompt or "— (не задан)"
    budget = format_cost(user.budget) if user.budget > 0 else "без лимита"
    text = (
        "👤 <b>Профиль</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{user.user_id}</code>\n"
        f"🧠 Модель: <b>{model.name}</b>\n"
        f"💰 Цена: <b>{model.price_str}</b>\n"
        f"🌡 Температура: <b>{user.temperature:.2f}</b>\n"
        f"📝 Системный промпт: <i>{prompt}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📨 Запросов: <b>{user.requests}</b>\n"
        f"🔢 Токенов (≈): <b>{format_tokens(user.tokens)}</b>\n"
        f"🪙 Потрачено: <b>{format_cost(user.cost)}</b>\n"
        f"💰 Бюджет: <b>{budget}</b>\n"
        f"📅 С нами с: <b>{user.created_at[:10]}</b>"
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
        f"🧹 Контекст очищен. Удалено сообщений: <b>{removed}</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu(is_admin),
    )
