"""Shared generation helpers used by text and media handlers."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from aiogram import Bot
from aiogram.enums import ChatAction, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import BufferedInputFile, Message

from bot.catalog import get_model, is_image_model
from bot.config import settings
from bot.database.db import Database
from bot.database.models import User
from bot.keyboards.inline import image_actions, image_models_keyboard
from bot.services.image import data_url_to_bytes, is_data_url
from bot.services.openrouter import (
    ChatMessage,
    OpenRouterClient,
    OpenRouterError,
    Usage,
    build_user_message,
)
from bot.services.pricing import PricingService, format_cost
from bot.services.tokens import estimate_messages_tokens, estimate_tokens, fit_messages
from bot.utils.text import markdown_to_html, split_html

logger = logging.getLogger(__name__)

_EDIT_INTERVAL = 1.4
_MAX_RETRIES = 2
_TAG_STRIP = re.compile(r"<[^>]+>")


async def _call_with_retry(coro_factory) -> bool:
    """Run an edit/send coroutine, retrying on flood control.

    ``TelegramRetryAfter`` is honoured with ``asyncio.sleep(retry_after)``.
    ``TelegramBadRequest`` for "message is not modified" is treated as success
    (the content is already on screen); a parse error falls back to plain text.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            await coro_factory(ParseMode.HTML)
            return True
        except TelegramRetryAfter as exc:
            logger.info("Flood control: sleeping %ss", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 0.5)
        except TelegramBadRequest as exc:
            message = str(exc).lower()
            if "message is not modified" in message:
                return True
            if "parse" in message and "entit" in message:
                try:
                    await coro_factory(None)
                    return True
                except (TelegramBadRequest, TelegramRetryAfter):
                    return False
            logger.debug("Telegram rejected edit: %s", exc)
            return False
        except Exception as exc:  # noqa: BLE001
            logger.debug("Unexpected edit error: %s", exc)
            return False
    return False


async def _safe_edit(message: Message, text: str) -> bool:
    """Edit a message with retry / parse fallback. Returns success."""
    return await _call_with_retry(
        lambda parse_mode: message.edit_text(text, parse_mode=parse_mode)
    )


async def _safe_send(bot: Bot, chat_id: int, text: str) -> bool:
    """Send a message with retry / parse fallback. Returns success."""
    return await _call_with_retry(
        lambda parse_mode: bot.send_message(chat_id, text, parse_mode=parse_mode)
    )


async def _render_answer(bot: Bot, chat_id: int, placeholder: Message, html_text: str) -> None:
    """Deliver an already-HTML answer, editing the placeholder for part one."""
    chunks = split_html(html_text)
    if not chunks:
        return
    await _safe_edit(placeholder, chunks[0])
    for chunk in chunks[1:]:
        await asyncio.sleep(0.15)
        await _safe_send(bot, chat_id, chunk)


def _build_messages(user: User, history, user_text: str, image_urls: list[str] | None):
    """Assemble a trimmed chat payload (system prompt + sliding window)."""
    messages: list[ChatMessage] = []
    if user.system_prompt:
        messages.append({"role": "system", "content": user.system_prompt})
    for item in history:
        messages.append({"role": item.role, "content": item.content})
    messages.append(build_user_message(user_text, image_urls))
    return fit_messages(list(messages), settings.max_context_tokens)


async def ensure_daily_limit(message: Message, db: Database, user: User) -> bool:
    """Enforce the per-user daily generation cap (admins are unlimited).

    Returns ``True`` when the request may proceed.
    """
    if user.id in settings.admin_ids:
        return True
    allowed, used = await db.consume_daily_message(user.id, settings.daily_message_limit)
    if allowed:
        return True
    await message.answer(
        f"Дневной лимит исчерпан ({used}/{settings.daily_message_limit} сообщений). "
        "Лимит обновится завтра."
    )
    return False


async def generate_and_reply(
    *,
    message: Message,
    db: Database,
    or_client: OpenRouterClient,
    pricing: PricingService,
    user: User,
    user_text: str,
    image_urls: list[str] | None = None,
) -> None:
    """Build the prompt, stream the answer and persist the turn."""
    if not await ensure_daily_limit(message, db, user):
        return

    if user.budget_exceeded:
        await message.answer(
            f"Достигнут лимит бюджета ({format_cost(user.budget)}). "
            "Измените лимит в настройках или очистите его."
        )
        return

    history = await db.get_history(user.id, settings.max_history_messages)
    messages = _build_messages(user, history, user_text, image_urls)

    if image_urls and user_text:
        stored_user = f"[изображение] {user_text}"
    elif image_urls:
        stored_user = "[изображение]"
    else:
        stored_user = user_text
    await db.add_message(user.id, "user", stored_user)

    placeholder = await message.answer("⏳ <i>Генерирую ответ…</i>", parse_mode=ParseMode.HTML)
    bot = message.bot
    chat_id = message.chat.id

    collected = ""
    usage: Usage | None = None
    last_edit = 0.0
    last_preview: str | None = None

    try:
        await bot.send_chat_action(chat_id, ChatAction.TYPING)
        async for chunk in or_client.stream_chat(
            messages,
            model=user.model,
            temperature=user.temperature,
            max_tokens=settings.max_output_tokens,
        ):
            if chunk.usage:
                usage = chunk.usage
            if not chunk.text:
                continue
            collected += chunk.text
            now = time.monotonic()
            if now - last_edit < _EDIT_INTERVAL:
                continue
            preview = collected[-3500:]
            if preview == last_preview:
                continue
            last_preview = preview
            last_edit = now
            await _safe_edit(placeholder, markdown_to_html(preview) + " ▌")
            await bot.send_chat_action(chat_id, ChatAction.TYPING)

    except OpenRouterError as exc:
        logger.warning("Generation failed: %s", exc)
        await _safe_edit(placeholder, exc.user_message)
        return

    if not collected.strip():
        await _safe_edit(placeholder, "🤷 Модель вернула пустой ответ.")
        return

    await _render_answer(bot, chat_id, placeholder, markdown_to_html(collected))
    await db.add_message(user.id, "assistant", collected)

    prompt_tokens = usage.prompt_tokens if usage else estimate_messages_tokens(list(messages))
    completion_tokens = usage.completion_tokens if usage else estimate_tokens(collected)
    total_tokens = (
        usage.total_tokens
        if usage and usage.total_tokens
        else prompt_tokens + completion_tokens
    )
    cost = await pricing.estimate_cost(
        user.model,
        prompt_tokens,
        completion_tokens,
        usage.cost if usage else None,
    )
    await db.increment_usage(
        user.id,
        requests=1,
        tokens=total_tokens,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost=cost,
    )


async def generate_image_and_reply(
    *,
    message: Message,
    db: Database,
    or_client: OpenRouterClient,
    pricing: PricingService,
    user: User,
    prompt: str,
) -> None:
    """Generate one or more images for *prompt* and deliver them."""
    if not is_image_model(user.model):
        model = get_model(user.model)
        await message.answer(
            f"🖼 Текущая модель <b>{model.name}</b> не поддерживает генерацию изображений.\n"
            "Выберите модель для рисования:",
            parse_mode=ParseMode.HTML,
            reply_markup=image_models_keyboard(user.model),
        )
        return

    if not await ensure_daily_limit(message, db, user):
        return

    if user.budget_exceeded:
        await message.answer(
            f"Достигнут лимит бюджета ({format_cost(user.budget)}). "
            "Измените лимит в настройках или очистите его."
        )
        return

    placeholder = await message.answer("🎨 Генерирую изображение…", parse_mode=ParseMode.HTML)
    bot = message.bot
    chat_id = message.chat.id

    try:
        await bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
        urls = await or_client.generate_image(
            prompt, model=user.model, max_tokens=settings.max_output_tokens
        )
    except OpenRouterError as exc:
        logger.warning("Image generation failed: %s", exc)
        await _safe_edit(placeholder, exc.user_message)
        return

    delivered = 0
    for index, url in enumerate(urls):
        try:
            if is_data_url(url):
                raw, _mime = data_url_to_bytes(url)
            else:
                raw = await or_client.fetch_bytes(url)
            photo = BufferedInputFile(raw, filename=f"image_{index + 1}.png")
            caption = None
            markup = None
            if index == len(urls) - 1:
                caption = f"🎨 <b>{_TAG_STRIP.sub('', prompt)[:200]}</b>"
                markup = image_actions(user.model)
            await message.answer_photo(
                photo,
                caption=caption,
                parse_mode=ParseMode.HTML if caption else None,
                reply_markup=markup,
            )
            delivered += 1
        except OpenRouterError as exc:
            await _safe_send(bot, chat_id, exc.user_message)
        except TelegramBadRequest as exc:
            logger.warning("Telegram rejected image: %s", exc)
            await _safe_send(bot, chat_id, "⚠️ Не удалось отправить изображение.")

    if delivered == 0:
        await _safe_edit(placeholder, "🤷 Не удалось получить изображение.")
        return

    try:
        await placeholder.delete()
    except TelegramBadRequest:
        pass

    await db.add_message(user.id, "user", f"[генерация изображения] {prompt}")
    image_tokens = estimate_tokens(prompt)
    cost = await pricing.estimate_image_cost(user.model, delivered, image_tokens)
    await db.increment_usage(
        user.id,
        requests=1,
        tokens=image_tokens + delivered * 100,
        prompt_tokens=image_tokens,
        completion_tokens=0,
        cost=cost,
    )
