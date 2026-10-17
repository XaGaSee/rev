"""Text helpers: HTML escaping, markdown-to-HTML, message splitting."""

from __future__ import annotations

import html
import re
from typing import Final

TELEGRAM_MESSAGE_LIMIT: Final[int] = 4096

_FENCED_CODE = re.compile(r"```([a-zA-Z0-9_+-]*)\n?(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+(.+)$")
_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^>]*)?/?>")


def escape_html(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    return html.escape(text, quote=False)


def markdown_to_html(text: str) -> str:
    """Best-effort conversion of common markdown to Telegram HTML.

    The input is escaped first, so the produced markup is always safe.
    """
    escaped = escape_html(text)
    escaped = _FENCED_CODE.sub(
        lambda m: f"<pre><code>{m.group(2).strip()}</code></pre>", escaped
    )
    escaped = _INLINE_CODE.sub(r"<code>\1</code>", escaped)
    escaped = _BOLD.sub(r"<b>\1</b>", escaped)
    escaped = _HEADING.sub(lambda m: f"<b>{m.group(1)}</b>", escaped)
    return escaped


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split *text* into chunks not exceeding *limit* characters.

    Splitting prefers paragraph, then line, then word boundaries.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        window = remaining[:limit]
        split_at = window.rfind("\n\n")
        if split_at < limit // 2:
            split_at = window.rfind("\n")
        if split_at < limit // 2:
            split_at = window.rfind(" ")
        if split_at <= 0:
            split_at = limit

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip("\n")

    return chunks


def truncate(text: str, length: int = 60) -> str:
    """Truncate *text* adding an ellipsis if needed."""
    text = " ".join(text.split())
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


def _is_closing(tag_token: str) -> bool:
    return tag_token.startswith("</")


def _is_self_closing(tag_token: str) -> bool:
    return tag_token.rstrip().endswith("/>")


def _tag_name(tag_token: str) -> str:
    name = tag_token[2:] if _is_closing(tag_token) else tag_token[1:]
    return name.split()[0].rstrip(">/").lower()


def _tokenize_html(text: str) -> list[tuple[bool, str]]:
    """Split *text* into ``(is_tag, token)`` pairs."""
    tokens: list[tuple[bool, str]] = []
    pos = 0
    for match in _TAG.finditer(text):
        if match.start() > pos:
            tokens.append((False, text[pos : match.start()]))
        tokens.append((True, match.group(0)))
        pos = match.end()
    if pos < len(text):
        tokens.append((False, text[pos:]))
    return tokens


def split_html(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split HTML into chunks <= *limit*, keeping tags balanced.

    Tags that are open at a chunk boundary are closed and re-opened in the
    following chunk, so Telegram never receives a half-cut ``<pre>``/``<code>``.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    open_tags: list[str] = []
    has_content = False

    def closers() -> str:
        return "".join(f"</{name}>" for name in reversed(open_tags))

    def openers() -> str:
        return "".join(f"<{name}>" for name in open_tags)

    def closers_len() -> int:
        return sum(len(name) + 3 for name in open_tags)

    def flush() -> None:
        nonlocal current, current_len, has_content
        if has_content and current:
            chunks.append("".join(current) + closers())
        reopened = openers()
        current = [reopened] if reopened else []
        current_len = len(reopened)
        has_content = False

    for is_tag, token in _tokenize_html(text):
        if is_tag:
            if not _is_closing(token) and not _is_self_closing(token):
                extra = len(token) + len(open_tags) * 3 + 8
                if has_content and current_len + extra + closers_len() > limit:
                    flush()
                open_tags.append(_tag_name(token))
                current.append(token)
                current_len += len(token)
            elif _is_closing(token):
                name = _tag_name(token)
                if name in open_tags:
                    while open_tags and open_tags[-1] != name:
                        open_tags.pop()
                    if open_tags:
                        open_tags.pop()
                current.append(token)
                current_len += len(token)
            else:
                current.append(token)
                current_len += len(token)
            continue

        remaining = token
        while remaining:
            available = limit - current_len - closers_len()
            if available <= 0:
                flush()
                remaining = remaining.lstrip("\n")
                if not remaining:
                    break
                available = limit - current_len - closers_len()
            if len(remaining) <= available:
                current.append(remaining)
                current_len += len(remaining)
                if remaining.strip():
                    has_content = True
                break

            window = remaining[:available]
            cut = window.rfind("\n\n")
            if cut < available // 2:
                cut = window.rfind("\n")
            if cut < available // 2:
                cut = window.rfind(" ")
            if cut <= 0:
                cut = available

            piece = remaining[:cut]
            if piece.strip():
                has_content = True
            current.append(piece)
            current_len += len(piece)
            flush()
            remaining = remaining[cut:].lstrip("\n")

    if has_content and current:
        chunks.append("".join(current) + closers())

    return chunks or [text[:limit]]
