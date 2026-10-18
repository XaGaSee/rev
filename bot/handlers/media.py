"""Media handlers: photos (vision) and voice messages (transcription)."""

from __future__ import annotations

import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message

from bot.config import settings
from bot.catalog import get_model, is_vision_model
from bot.database.db import Database
from bot.database.models import User
from bot.handlers.common import generate_and_reply
from bot.keyboards.inline import models_categories
from bot.services.audio import voice_filename
from bot.services.image import bytes_to_data_url, guess_mime
from bot.services.openrouter import OpenRouterClient, OpenRouterError
from bot.services.pricing import PricingService
from bot.utils.text import escape_html

logger = logging.getLogger(__name__)

router = Router(name="media")

_MAX_VOICE_BYTES = 20 * 1024 * 1024


async def _download(bot, file_id: str) -> bytes:
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
        await message.answer(
            "👁️ Текущая модель <b>{}</b> не умеет анализировать изображения.\n"
            "Выберите модель из категории «Анализ изображений».".format(
                get_model(user.model).name
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=models_categories(),
        )
        return

    caption = (message.caption or "Опиши подробно, что изображено на этом фото.").strip()
    largest = message.photo[-1]
    try:
        raw = await _download(message.bot, largest.file_id)
    except (TelegramBadRequest, ValueError) as exc:
        logger.warning("Failed to download photo: %s", exc)
        await message.answer("⚠️ Не удалось загрузить изображение. Попробуйте ещё раз.")
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
        await message.answer("⚠️ Голосовое сообщение слишком большое (лимит 20 МБ).")
        return
    if user.id not in settings.admin_ids and not await db.has_daily_quota(
        user.id, settings.daily_message_limit
    ):
        limit = settings.daily_message_limit
        await message.answer(
            f"Дневной лимит исчерпан ({limit}/{limit} сообщений). Лимит обновится завтра."
        )
        return
    try:
        raw = await _download(message.bot, voice.file_id)
    except (TelegramBadRequest, ValueError) as exc:
        logger.warning("Failed to download voice: %s", exc)
        await message.answer("⚠️ Не удалось загрузить голосовое сообщение.")
        return

    status = await message.answer("🎙 <i>Распознаю речь…</i>", parse_mode=ParseMode.HTML)
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
        await status.edit_text(exc.user_message)
        return

    try:
        await status.edit_text(
            f"🎙 <b>Распознано:</b>\n<i>{escape_html(transcript)}</i>",
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
