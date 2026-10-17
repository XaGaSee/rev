"""Audio helpers for voice transcription."""

from __future__ import annotations


def voice_filename(file_unique_id: str | None) -> str:
    """Return a stable filename for a Telegram voice note."""
    suffix = (file_unique_id or "voice")[:24]
    return f"{suffix}.ogg"
