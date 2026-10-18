"""Curated OpenRouter model catalog grouped by category.

Every model exposes ``price_str`` (human readable), a compact ``price_short``
badge and capability suffixes used across the UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    """A single selectable model."""

    id: str
    name: str
    category: str
    price_str: str
    supports_vision: bool = False
    supports_image_generation: bool = False

    @property
    def price_short(self) -> str:
        """Compact price badge: ``[Free]``, ``[$0.14/1M]`` or ``[$0.003]``."""
        low = self.price_str.lower()
        if "беспл" in low or "free" in low:
            return "[Free]"
        amounts = re.findall(r"\$[\d.]+", self.price_str)
        if not amounts:
            return ""
        if "шт" in low or "изображ" in low:
            return f"[{amounts[0]}]"
        return f"[{amounts[0]}/1M]"

    @property
    def label(self) -> str:
        """Display name with the price badge."""
        return f"{self.name} {self.price_short}".strip()

    @property
    def catalog_label(self) -> str:
        """Catalog label with a capability suffix: ``[Vision]`` / ``[Img]``."""
        if self.supports_vision:
            cap = " [Vision]"
        elif self.supports_image_generation:
            cap = " [Img]"
        else:
            cap = ""
        return f"{self.label}{cap}"


@dataclass(frozen=True)
class Category:
    """A model category."""

    key: str
    title: str


CATEGORIES: tuple[Category, ...] = (
    Category("fast", "Быстрые"),
    Category("reasoning", "Мультимодальные"),
    Category("image_gen", "Изображения"),
)

MODELS: tuple[ModelInfo, ...] = (
    # --- Fast ---
    ModelInfo("deepseek/deepseek-v4.1-flash", "DeepSeek V4.1", "fast", "$0.14 / $0.28 за 1M"),
    ModelInfo("deepseek/deepseek-v4.1-flash:free", "DeepSeek V4.1", "fast", "Бесплатно"),
    ModelInfo("mimo/mimo-2.6-flash", "MiMo 2.6 Flash", "fast", "$0.10 / $0.30 за 1M"),
    ModelInfo("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B", "fast", "$0.35 / $0.40 за 1M"),
    ModelInfo(
        "qwen/qwen-3-vl", "Qwen 3 VL", "fast", "$0.20 / $0.60 за 1M", supports_vision=True
    ),
    # --- Multimodal / reasoning ---
    ModelInfo(
        "nvidia/nemotron-3.5-super-vl:free",
        "Nemotron 3.5 VL",
        "reasoning",
        "Бесплатно",
        supports_vision=True,
    ),
    ModelInfo("dots-studio/dots3-note-preview:free", "Dots3 Note", "reasoning", "Бесплатно"),
    ModelInfo(
        "deepseek/deepseek-v4.1-reasoner",
        "DeepSeek V4.1 Reasoner",
        "reasoning",
        "$0.55 / $2.20 за 1M",
    ),
    # --- Image generation ---
    ModelInfo(
        "black-forest-labs/flux-1-schnell",
        "FLUX.1 Schnell",
        "image_gen",
        "$0.003 / изображение",
        supports_image_generation=True,
    ),
    ModelInfo(
        "stabilityai/stable-diffusion-3.5-large",
        "SD 3.5 Large",
        "image_gen",
        "$0.065 / изображение",
        supports_image_generation=True,
    ),
)

MODEL_MAP: dict[str, ModelInfo] = {m.id: m for m in MODELS}
DEFAULT_MODEL_INFO: ModelInfo = MODEL_MAP["nvidia/nemotron-3.5-super-vl:free"]
DEFAULT_MODEL_ID: str = DEFAULT_MODEL_INFO.id


def models_by_category(category: str) -> list[ModelInfo]:
    """Return all models belonging to *category*."""
    return [m for m in MODELS if m.category == category]


def get_model(model_id: str) -> ModelInfo:
    """Return :class:`ModelInfo` for *model_id* or the default model."""
    return MODEL_MAP.get(model_id, DEFAULT_MODEL_INFO)


def is_image_model(model_id: str) -> bool:
    """Whether *model_id* generates images instead of text."""
    return get_model(model_id).supports_image_generation


def is_vision_model(model_id: str) -> bool:
    """Whether *model_id* accepts image inputs."""
    return get_model(model_id).supports_vision


def image_models() -> list[ModelInfo]:
    """Return every image generation model."""
    return models_by_category("image_gen")


def vision_models() -> list[ModelInfo]:
    """Return every model that accepts image inputs."""
    return [m for m in MODELS if m.supports_vision]


def search_models(query: str) -> list[ModelInfo]:
    """Case-insensitive search over model id and name."""
    needle = query.strip().lower()
    if not needle:
        return []
    return [m for m in MODELS if needle in m.id.lower() or needle in m.name.lower()]