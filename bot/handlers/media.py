"""Media handlers: photos (vision) and voice messages (transcription)."""

from __future__ import annotations

import logging
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message

from bot.data.catalog import get_model, is_vision_model
from bot.config import settings
from bot.database.db import Database
from bot.database.models import User
from bot.handlers.common import generate_and_reply
from bot.keyboards.inline import vision_models_keyboard
from bot.services.audio import voice_filename
from bot.services.image import bytes_to_data_url, guess_mime
from bot.services.openrouter import OpenRouterClient, OpenRouterError
from bot.services.pricing import PricingService
from bot.utils.text import escape_html

logger = logging.getLogger(__name__)

router = Router(name="media")

_MAX_VOICE_BYTES = 20 * 1024 * 1024


async def _download(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    if file.file_path is None:
        raise ValueError("Telegram returned no file path")
    buffer = BytesIO()
    await bot.download_file(file.file_path, buffer)
    return buffer.getvalue()


@router.message(F.photo)
async def handle_photo(
    message: Message,
    db: Database,
    or_client: OpenRouterClient,
    pricing: PricingService,
    user: User,
) -> None:
    """Analyse an image using a vision-capable model."""
    if not is_vision_model(user.model):
        model = get_model(user.model)
        await message.answer(
            f"Модель {model.label} не поддерживает анализ изображений.\n"
            "Выберите vision-модель:",
            reply_markup=vision_models_keyboard(user.model),
        )
        return

    caption = (message.caption or "Опишите содержимое изображения.").strip()
    largest = message.photo[-1]
    try:
        raw = await _download(message.bot, largest.file_id)
    except (TelegramBadRequest, ValueError) as exc:
        logger.warning("Failed to download photo: %s", exc)
        await message.answer("Не удалось загрузить изображение. Попробуйте ещё раз.")
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    data_url = bytes_to_data_url(raw, guess_mime("photo.jpg"))
    await generate_and_reply(
        message=message,
        db=db,
        or_client=or_client,
        pricing=pricing,
        user=user,
        user_text=caption,
        image_urls=[data_url],
    )


@router.message(F.voice)
async def handle_voice(
    message: Message,
    db: Database,
    or_client: OpenRouterClient,
    pricing: PricingService,
    user: User,
) -> None:
    """Transcribe a voice message then answer with the active model."""
    voice = message.voice
    assert voice is not None
    if voice.file_size and voice.file_size > _MAX_VOICE_BYTES:
        await message.answer("Голосовое сообщение превышает лимит 20 МБ.")
        return
    if user.user_id not in settings.admin_ids and not await db.has_daily_quota(
        user.user_id, settings.daily_message_limit
    ):
        limit = settings.daily_message_limit
        await message.answer(
            f"Суточный лимит запросов ({limit}/{limit}) исчерпан. "
            "Доступ обновится в 00:00 UTC."
        )
        return
    try:
        raw = await _download(message.bot, voice.file_id)
    except (TelegramBadRequest, ValueError) as exc:
        logger.warning("Failed to download voice: %s", exc)
        await message.answer("Не удалось загрузить голосовое сообщение.")
        return

    status = await message.answer("Распознавание речи…")
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        transcript = await or_client.transcribe(
            base_url=settings.transcription_base_url,
            api_key=settings.transcription_key,
            model=settings.transcription_model,
            audio=raw,
            filename=voice_filename(voice.file_unique_id),
        )
    except OpenRouterError as exc:
        try:
            await status.edit_text(exc.user_message, parse_mode=ParseMode.HTML)
        except (TelegramBadRequest, TelegramRetryAfter):
            pass
        return

    try:
        await status.edit_text(
            f"Расшифровка: {escape_html(transcript)}",
            parse_mode=ParseMode.HTML,
        )
    except (TelegramBadRequest, TelegramRetryAfter):
        pass

    await generate_and_reply(
        message=message,
        db=db,
        or_client=or_client,
        pricing=pricing,
        user=user,
        user_text=transcript,
    )
