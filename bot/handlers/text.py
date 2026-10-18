"""Plain text message handler."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.catalog import is_image_model
from bot.database.db import Database
from bot.database.models import User
from bot.handlers.common import generate_and_reply, generate_image_and_reply
from bot.services.openrouter import OpenRouterClient
from bot.services.pricing import PricingService
from bot.states import ImageStates

router = Router(name="text")


@router.message(ImageStates.prompt, F.text)
async def handle_image_prompt(
    message: Message,
    state: FSMContext,
    db: Database,
    or_client: OpenRouterClient,
    pricing: PricingService,
    user: User,
) -> None:
    """Handle a prompt captured through the image generation flow."""
    await state.clear()
    prompt = (message.text or "").strip()
    if not prompt:
        await message.answer("✖️ Пустой запрос. Попробуйте снова.")
        return
    await generate_image_and_reply(
        message=message, db=db, or_client=or_client, pricing=pricing, user=user, prompt=prompt
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(
    message: Message,
    db: Database,
    or_client: OpenRouterClient,
    pricing: PricingService,
    user: User,
) -> None:
    """Route free-form text to either image generation or chat."""
    text = message.text or ""
    if is_image_model(user.model):
        await generate_image_and_reply(
            message=message, db=db, or_client=or_client, pricing=pricing, user=user, prompt=text
        )
        return
    await generate_and_reply(
        message=message,
        db=db,
        or_client=or_client,
        pricing=pricing,
        user=user,
        user_text=text,
    )
