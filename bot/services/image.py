"""Image helpers: base64 data URIs and downloads."""

from __future__ import annotations

import base64

_MIME_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
}


def guess_mime(filename: str | None, default: str = "image/jpeg") -> str:
    """Guess an image mime type from a file name / path."""
    if not filename:
        return default
    ext = filename.rsplit(".", 1)[-1].lower()
    return _MIME_BY_EXT.get(ext, default)


def bytes_to_data_url(data: bytes, mime: str = "image/jpeg") -> str:
    """Encode raw image bytes as a base64 ``data:`` URL."""
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def is_data_url(url: str) -> bool:
    """Whether *url* is a base64 data URI."""
    return url.startswith("data:")


def data_url_to_bytes(data_url: str) -> tuple[bytes, str]:
    """Decode a base64 ``data:`` URL into ``(bytes, mime)``."""
    header, _, payload = data_url.partition(",")
    mime = header[5:].split(";")[0] or "image/png"
    return base64.b64decode(payload), mime
