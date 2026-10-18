"""Command handlers: /start, /help, /menu, /profile, /model, /reset."""

from __future__ import annotations

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.catalog import get_model
from bot.database.db import Database
from bot.database.models import User
from bot.keyboards.inline import main_menu
from bot.services.pricing import format_cost
from bot.services.tokens import format_tokens
from bot.ui import HELP_TEXT, get_main_menu_payload, get_models_payload, get_profile_payload

router = Router(name="commands")


async def send_main_menu(message: Message, user: User, is_admin: bool) -> None:
    """Render the main screen through the shared payload builder."""
    text, markup = get_main_menu_payload(user, is_admin)
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)


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
    text, markup = get_profile_payload(user, is_admin)
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)


@router.message(Command("model"))
async def cmd_model(message: Message) -> None:
    text, markup = get_models_payload()
    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=markup)


@router.message(Command("reset"))
async def cmd_reset(message: Message, db: Database, user: User, is_admin: bool) -> None:
    removed = await db.clear_history(user.user_id)
    await message.answer(
        f"Контекст очищен ({removed} сообщений).",
        reply_markup=main_menu(is_admin),
    )