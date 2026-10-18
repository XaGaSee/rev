"""Async OpenRouter client with streaming, vision and image generation support."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable, Mapping, Sequence

import aiohttp

logger = logging.getLogger(__name__)

ChatMessage = Mapping[str, Any]


class OpenRouterError(Exception):
    """Base class for OpenRouter integration failures."""

    user_message = "Не удалось выполнить запрос. Попробуйте позже."


class AuthError(OpenRouterError):
    user_message = "🔑 Ошибка авторизации API ключа."


class InsufficientCreditsError(OpenRouterError):
    user_message = "💳 Недостаточно кредитов на балансе OpenRouter API."


class RateLimitError(OpenRouterError):
    user_message = "⏳ Превышен лимит запросов к провайдеру. Повторите попытку через минуту."


class UpstreamError(OpenRouterError):
    user_message = "Сервис модели временно недоступен. Попробуйте позже."


class NetworkError(OpenRouterError):
    user_message = "Ошибка сети. Проверьте соединение и повторите запрос."


class BadRequestError(OpenRouterError):
    user_message = "Запрос отклонён моделью. Возможно, этот ввод не поддерживается."


@dataclass(slots=True)
class Usage:
    """Token usage reported by the provider."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "Usage":
        if not data:
            return cls()
        raw_cost = data.get("cost")
        try:
            cost = float(raw_cost) if raw_cost is not None else None
        except (TypeError, ValueError):
            cost = None
        return cls(
            prompt_tokens=int(data.get("prompt_tokens", 0) or 0),
            completion_tokens=int(data.get("completion_tokens", 0) or 0),
            total_tokens=int(data.get("total_tokens", 0) or 0),
            cost=cost,
        )


@dataclass(slots=True)
class StreamChunk:
    """A single streamed event."""

    text: str = ""
    usage: Usage | None = None


@dataclass(slots=True)
class ChatResult:
    """Final result of a non-streaming completion."""

    text: str
    usage: Usage


class OpenRouterClient:
    """Minimal, dependency-light OpenRouter REST client."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        app_name: str = "OpenRouter Telegram Bot",
        app_url: str = "https://openrouter.ai",
        request_timeout: int = 300,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._app_name = app_name
        self._app_url = app_url
        self._timeout = aiohttp.ClientTimeout(total=None, connect=20, sock_read=request_timeout)
        self._session: aiohttp.ClientSession | None = None

    # ---------------------------------------------------------------- session
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._app_url,
            "X-Title": self._app_name,
        }

    # ------------------------------------------------------------------ errors
    @staticmethod
    def _raise_for_status(status: int, body: str) -> None:
        if status < 400:
            return
        detail = body[:500]
        try:
            parsed = json.loads(body)
            detail = parsed.get("error", {}).get("message", detail)
        except (ValueError, AttributeError):
            pass

        logger.warning("OpenRouter HTTP %s: %s", status, detail)
        if status in (401, 403):
            raise AuthError(detail)
        if status == 402:
            raise InsufficientCreditsError(detail)
        if status == 429:
            raise RateLimitError(detail)
        if status in (400, 404, 422):
            raise BadRequestError(detail)
        if status >= 500:
            raise UpstreamError(detail)
        raise OpenRouterError(detail)

    # -------------------------------------------------------------------- chat
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        """Perform a blocking chat completion."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        session = await self._get_session()
        try:
            async with session.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                body = await response.text()
                self._raise_for_status(response.status, body)
                data = json.loads(body)
        except aiohttp.ClientError as exc:
            logger.exception("Network error while calling OpenRouter")
            raise NetworkError(str(exc)) from exc
        except TimeoutError as exc:
            raise NetworkError(str(exc)) from exc

        choices = data.get("choices") or []
        if not choices:
            raise UpstreamError("Empty choices in response")
        message = choices[0].get("message", {})
        text = message.get("content") or ""
        if isinstance(text, list):
            text = "".join(
                part.get("text", "")
                for part in text
                if isinstance(part, dict) and part.get("type") == "text"
            )
        return ChatResult(text=text, usage=Usage.from_dict(data.get("usage")))

    async def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion as :class:`StreamChunk` events."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        session = await self._get_session()
        try:
            async with session.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    self._raise_for_status(response.status, body)

                async for raw_line in response.content:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[len("data:") :].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                    except ValueError:
                        continue

                    usage = event.get("usage")
                    if usage:
                        yield StreamChunk(usage=Usage.from_dict(usage))

                    for choice in event.get("choices") or []:
                        delta = choice.get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            yield StreamChunk(text=piece)
        except aiohttp.ClientError as exc:
            logger.exception("Network error while streaming from OpenRouter")
            raise NetworkError(str(exc)) from exc
        except TimeoutError as exc:
            raise NetworkError(str(exc)) from exc

    # ----------------------------------------------------------- image gen
    async def generate_image(
        self,
        prompt: str,
        model: str,
        max_tokens: int | None = None,
    ) -> list[str]:
        """Generate images and return a list of URLs / data URIs."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        session = await self._get_session()
        try:
            async with session.post(
                f"{self._base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                body = await response.text()
                self._raise_for_status(response.status, body)
                data = json.loads(body)
        except aiohttp.ClientError as exc:
            logger.exception("Network error while generating image")
            raise NetworkError(str(exc)) from exc
        except TimeoutError as exc:
            raise NetworkError(str(exc)) from exc

        choices = data.get("choices") or []
        if not choices:
            raise UpstreamError("Empty choices in image response")

        message = choices[0].get("message", {})
        urls: list[str] = []
        for item in message.get("images") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "image_url":
                url = (item.get("image_url") or {}).get("url")
            else:
                url = item.get("url")
            if url:
                urls.append(url)

        if not urls:
            text = message.get("content")
            if isinstance(text, str) and text.strip():
                raise BadRequestError(
                    "Модель вернула текст вместо изображения: " + text.strip()[:300]
                )
            raise UpstreamError("Модель не вернула изображение")
        return urls

    async def transcribe(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        audio: bytes,
        filename: str = "voice.ogg",
        language: str | None = None,
    ) -> str:
        """Transcribe audio using an OpenAI-compatible endpoint."""
        form = aiohttp.FormData()
        form.add_field("file", audio, filename=filename, content_type="audio/ogg")
        form.add_field("model", model)
        if language:
            form.add_field("language", language)

        session = await self._get_session()
        try:
            async with session.post(
                f"{base_url.rstrip('/')}/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=form,
            ) as response:
                body = await response.text()
                self._raise_for_status(response.status, body)
                data = json.loads(body)
        except aiohttp.ClientError as exc:
            logger.exception("Network error while transcribing audio")
            raise NetworkError(str(exc)) from exc
        except TimeoutError as exc:
            raise NetworkError(str(exc)) from exc

        text = data.get("text")
        if not text:
            raise UpstreamError("Пустой результат транскрибации")
        return text

    async def fetch_bytes(self, url: str) -> bytes:
        """Download binary content from a URL (used for generated images)."""
        session = await self._get_session()
        try:
            async with session.get(url) as response:
                data = await response.read()
                if response.status >= 400:
                    body = data[:500].decode("utf-8", errors="ignore")
                    self._raise_for_status(response.status, body)
                return data
        except aiohttp.ClientError as exc:
            raise NetworkError(str(exc)) from exc
        except TimeoutError as exc:
            raise NetworkError(str(exc)) from exc

    async def list_models(self) -> list[dict[str, Any]]:
        """Fetch the OpenRouter model catalog with pricing."""
        session = await self._get_session()
        try:
            async with session.get(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                body = await response.text()
                self._raise_for_status(response.status, body)
                data = json.loads(body)
        except aiohttp.ClientError as exc:
            raise NetworkError(str(exc)) from exc
        except TimeoutError as exc:
            raise NetworkError(str(exc)) from exc
        return list(data.get("data") or [])


def build_user_message(text: str, image_data_urls: Iterable[str] | None = None) -> ChatMessage:
    """Build a user message, optionally multimodal (vision)."""
    images = list(image_data_urls or [])
    if not images:
        return {"role": "user", "content": text}
    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    for url in images:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return {"role": "user", "content": content}
