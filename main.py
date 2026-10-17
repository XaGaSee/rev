"""Application entry point."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from bot.config import settings
from bot.database.db import Database
from bot.handlers import admin, callbacks, commands, media, text
from bot.middlewares.locking import ConcurrencyGuard, ConcurrencyMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.middlewares.user import UserMiddleware
from bot.services.openrouter import OpenRouterClient
from bot.services.pricing import PricingService

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="start", description="🏠 Главное меню"),
    BotCommand(command="menu", description="📋 Меню"),
    BotCommand(command="model", description="⚙️ Выбрать модель"),
    BotCommand(command="profile", description="👤 Профиль"),
    BotCommand(command="reset", description="🧹 Очистить контекст"),
    BotCommand(command="help", description="❓ Помощь"),
]


async def on_error(event: ErrorEvent) -> None:
    """Last-resort error handler."""
    logger.exception("Unhandled error: %s", event.exception, exc_info=event.exception)
    update = event.update
    try:
        if update.message is not None:
            await update.message.answer("⚠️ Произошла внутренняя ошибка. Мы уже чиним её.")
        elif update.callback_query is not None:
            await update.callback_query.answer("⚠️ Внутренняя ошибка", show_alert=True)
    except Exception:  # noqa: BLE001
        logger.debug("Failed to notify user about the error")


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    db = Database(settings.database_path)
    await db.connect()

    or_client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        app_name=settings.openrouter_app_name,
        app_url=settings.openrouter_app_url,
    )
    pricing = PricingService(db, or_client)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(
        storage=MemoryStorage(),
        db=db,
        or_client=or_client,
        pricing=pricing,
    )

    throttling = ThrottlingMiddleware(rate=settings.throttling_rate)
    user_mw = UserMiddleware(db)
    concurrency = ConcurrencyMiddleware(ConcurrencyGuard())
    dp.message.middleware(throttling)
    dp.message.middleware(user_mw)
    dp.message.middleware(concurrency)
    dp.callback_query.middleware(throttling)
    dp.callback_query.middleware(user_mw)

    # Order matters: admin & FSM routers first, then navigation, then fallbacks.
    dp.include_router(admin.router)
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(media.router)
    dp.include_router(text.router)

    dp.errors.register(on_error)

    async def on_shutdown() -> None:
        await or_client.close()
        await db.close()

    dp.shutdown.register(on_shutdown)

    await bot.set_my_commands(BOT_COMMANDS)
    await bot.delete_webhook(drop_pending_updates=True)

    async def warm_pricing() -> None:
        try:
            await pricing.ensure_loaded()
        except Exception:  # noqa: BLE001
            logger.exception("Pricing warm-up failed")

    pricing_task = asyncio.create_task(warm_pricing())

    logger.info("Bot started. Admins: %s", settings.admin_ids or "none")
    try:
        await dp.start_polling(bot)
    finally:
        pricing_task.cancel()
        await on_shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
