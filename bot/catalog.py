"""Curated OpenRouter model catalog grouped by category.

Every model exposes ``price_str`` (human readable, e.g. ``"Бесплатно"`` or
``"$0.15 / $0.60 за 1M"``), ``supports_vision`` and
``supports_image_generation`` flags used across the UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ModelInfo:
    """A single selectable model."""

    id: str
    name: str
    category: str
    price_str: str
    supports_vision: bool = False
    supports_image_generation: bool = False
    description: str = ""

    @property
    def price_short(self) -> str:
        """Compact price tag for inline buttons, e.g. ``($0.15/1M)``."""
        low = self.price_str.lower()
        if "беспл" in low or "free" in low:
            return "(Free)"
        match = re.search(r"\$[\d.]+", self.price_str)
        if not match:
            return ""
        value = match.group(0)
        if "шт" in low or "изображ" in low:
            return f"({value}/img)"
        return f"({value}/1M)"

    @property
    def label(self) -> str:
        """Button label: name plus a compact price tag."""
        tag = self.price_short
        return f"{self.name} {tag}".strip()


@dataclass(frozen=True)
class Category:
    """A model category."""

    key: str
    title: str
    icon: str


CATEGORIES: tuple[Category, ...] = (
    Category("fast", "Быстрые / Экономные", "🚀"),
    Category("reasoning", "Умные / Мультимодальные", "🧠"),
    Category("image_gen", "Генерация изображений", "🎨"),
)

CATEGORY_MAP: dict[str, Category] = {c.key: c for c in CATEGORIES}

MODELS: tuple[ModelInfo, ...] = (
    # --- Fast / cheap ---
    ModelInfo(
        "deepseek/deepseek-v4.1-flash",
        "DeepSeek V4.1 Flash",
        "fast",
        "$0.14 / $0.28 за 1M",
        description="Быстрая и недорогая",
    ),
    ModelInfo(
        "deepseek/deepseek-v4.1-flash:free",
        "DeepSeek V4.1 Flash",
        "fast",
        "Бесплатно",
        description="Бесплатная версия",
    ),
    ModelInfo(
        "mimo/mimo-2.6-flash",
        "MiMo 2.6 Flash",
        "fast",
        "$0.10 / $0.30 за 1M",
        description="Лёгкая и быстрая",
    ),
    ModelInfo(
        "qwen/qwen-2.5-72b-instruct",
        "Qwen 2.5 72B",
        "fast",
        "$0.35 / $0.40 за 1M",
        description="Мультиязычная",
    ),
    ModelInfo(
        "qwen/qwen-3-vl",
        "Qwen 3 VL",
        "fast",
        "$0.20 / $0.60 за 1M",
        supports_vision=True,
        description="Vision + текст",
    ),
    # --- Smart / multimodal (vision + reasoning) ---
    ModelInfo(
        "nvidia/nemotron-3.5-super-vl:free",
        "NVIDIA Nemotron 3.5 Super VL",
        "reasoning",
        "Бесплатно",
        supports_vision=True,
        description="Бесплатно, 1M контекст, vision",
    ),
    ModelInfo(
        "dots-studio/dots3-note-preview:free",
        "Dots3 Note Preview",
        "reasoning",
        "Бесплатно",
        description="Бесплатно, 512K контекст",
    ),
    ModelInfo(
        "deepseek/deepseek-v4.1-reasoner",
        "DeepSeek V4.1 Reasoner",
        "reasoning",
        "$0.55 / $2.20 за 1M",
        description="Пошаговые рассуждения",
    ),
    # --- Image generation ---
    ModelInfo(
        "black-forest-labs/flux-1-schnell",
        "FLUX.1 Schnell",
        "image_gen",
        "$0.003 / изображение",
        supports_image_generation=True,
        description="Быстрая генерация картинок",
    ),
    ModelInfo(
        "stabilityai/stable-diffusion-3.5-large",
        "Stable Diffusion 3.5 Large",
        "image_gen",
        "$0.065 / изображение",
        supports_image_generation=True,
        description="Качественная генерация",
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


def search_models(query: str) -> list[ModelInfo]:
    """Case-insensitive search over model id and name."""
    needle = query.strip().lower()
    if not needle:
        return []
    return [m for m in MODELS if needle in m.id.lower() or needle in m.name.lower()]


def iter_models() -> Iterable[ModelInfo]:
    """Iterate over every catalogued model."""
    return iter(MODELS)
