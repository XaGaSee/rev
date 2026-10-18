"""Admin handlers: statistics and broadcast."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database.db import Database
from bot.keyboards.inline import admin_menu, back_to_menu, cancel
from bot.services.pricing import PricingService, format_cost
from bot.services.tokens import format_tokens
from bot.states import AdminStates

logger = logging.getLogger(__name__)

router = Router(name="admin")

router.message.filter(F.from_user.id.in_(settings.admin_ids))  # type: ignore[union-attr]
router.callback_query.filter(F.from_user.id.in_(settings.admin_ids))  # type: ignore[union-attr]


async def _stats_text(db: Database) -> str:
    stats = await db.get_stats()
    return (
        f"👥 Пользователей: {stats.users} · сегодня: {stats.active_today}\n"
        f"📨 Запросов: {format_tokens(stats.requests)}\n"
        f"🔢 Токены: вход {format_tokens(stats.prompt_tokens)} / "
        f"выход {format_tokens(stats.completion_tokens)}\n"
        f"🪙 Расход: <b>{format_cost(stats.cost)}</b>"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer("Админка", reply_markup=admin_menu())


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database) -> None:
    await message.answer(await _stats_text(db), parse_mode=ParseMode.HTML, reply_markup=admin_menu())


@router.message(Command("resetlimit"))
async def cmd_reset_limit(message: Message, db: Database) -> None:
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /resetlimit <user_id>")
        return
    ok = await db.reset_daily_limit(int(parts[1]))
    await message.answer("Лимит сброшен." if ok else "Пользователь не найден.")


@router.message(Command("pricing"))
async def cmd_pricing(message: Message, pricing: PricingService) -> None:
    status = await message.answer("Обновляю прайс-лист…", parse_mode=ParseMode.HTML)
    try:
        count = await pricing.refresh()
    except Exception:  # noqa: BLE001
        logger.exception("Pricing refresh failed")
        await status.edit_text("Не удалось обновить прайс-лист. Попробуйте позже.")
        return
    updated = await pricing.last_updated()
    await status.edit_text(
        f"Прайс-лист обновлён: моделей {count}, время <code>{updated or '—'}</code>",
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "admin:stats")
async def cb_stats(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(
            await _stats_text(db), parse_mode=ParseMode.HTML, reply_markup=admin_menu()
        )
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.broadcast)
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(
            "Рассылка\n\nОтправьте текст сообщения для всех пользователей (HTML).",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel("menu:admin"),
        )
    except TelegramBadRequest:
        pass


@router.message(AdminStates.broadcast, F.text)
async def do_broadcast(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    text = message.html_text or (message.text or "")
    user_ids = await db.all_user_ids()

    sent = 0
    failed = 0
    for user_id in user_ids:
        try:
            await message.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await message.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
                sent += 1
            except Exception:  # noqa: BLE001
                failed += 1
        except TelegramForbiddenError:
            failed += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Broadcast to %s failed: %s", user_id, exc)
            failed += 1
        await asyncio.sleep(0.1)

    await message.answer(
        f"Рассылка завершена: доставлено {sent}, ошибок {failed}.",
        reply_markup=back_to_menu(),
    )
