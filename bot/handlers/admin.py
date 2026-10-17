"""Admin handlers: statistics and broadcast."""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
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
        "📊 <b>Статистика</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей: <b>{stats.users}</b>\n"
        f"📨 Запросов: <b>{stats.requests}</b>\n"
        f"🔢 Токенов (≈): <b>{format_tokens(stats.tokens)}</b>\n"
        f"🪙 Расходы (≈): <b>{format_cost(stats.cost)}</b>"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer("🛡 <b>Админ-панель</b>", parse_mode=ParseMode.HTML, reply_markup=admin_menu())


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database) -> None:
    await message.answer(await _stats_text(db), parse_mode=ParseMode.HTML, reply_markup=admin_menu())


@router.message(Command("pricing"))
async def cmd_pricing(message: Message, pricing: PricingService) -> None:
    status = await message.answer("🔄 Обновляю прайс-лист OpenRouter…", parse_mode=ParseMode.HTML)
    try:
        count = await pricing.refresh()
    except Exception as exc:  # noqa: BLE001
        await status.edit_text(f"⚠️ Не удалось обновить прайс: {exc}", parse_mode=ParseMode.HTML)
        return
    updated = await pricing.last_updated()
    await status.edit_text(
        "🪙 <b>Прайс-лист обновлён</b>\n"
        f"Моделей: <b>{count}</b>\n"
        f"Время: <code>{updated or '—'}</code>",
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data == "admin:stats")
async def cb_stats(callback: CallbackQuery, db: Database) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(  # type: ignore[union-attr]
            await _stats_text(db), parse_mode=ParseMode.HTML, reply_markup=admin_menu()
        )


@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminStates.broadcast)
    if callback.message:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📢 <b>Рассылка</b>\n\nОтправьте текст сообщения для всех пользователей.\n"
            "Поддерживается HTML-разметка.",
            parse_mode=ParseMode.HTML,
            reply_markup=cancel("menu:admin"),
        )


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
        await asyncio.sleep(0.05)

    await message.answer(
        f"📢 <b>Рассылка завершена</b>\n"
        f"✅ Доставлено: <b>{sent}</b>\n"
        f"⚠️ Ошибок: <b>{failed}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_menu(),
    )
