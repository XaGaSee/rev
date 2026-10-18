"""Curated OpenRouter model catalog (2026) grouped by category.

Prices are USD per 1M tokens (``price_in`` / ``price_out``) or per generated
image (``price_image``). Button labels use the compact badge format:
``DeepSeek V4.1 [$0.14/$0.28]`` / ``NVIDIA Nemotron 3.5 Super VL [Free]``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    """A single selectable model."""

    id: str
    name: str
    category: str
    price_in: float = 0.0
    price_out: float = 0.0
    price_image: float = 0.0
    supports_vision: bool = False
    supports_image_generation: bool = False

    @property
    def is_free(self) -> bool:
        """Whether the model costs nothing to run."""
        return self.price_in == 0 and self.price_out == 0 and self.price_image == 0

    @property
    def price_str(self) -> str:
        """Human readable tariff line used on detail screens."""
        if self.supports_image_generation:
            return f"${self.price_image:g} / изображение"
        if self.is_free:
            return "Бесплатно"
        return f"${self.price_in:.2f} / ${self.price_out:.2f} за 1M"

    @property
    def price_short(self) -> str:
        """Compact price badge for buttons."""
        if self.supports_image_generation:
            return f"[${self.price_image:g}]"
        if self.is_free:
            return "[Free]"
        return f"[${self.price_in:.2f}/${self.price_out:.2f}]"

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
    Category("fast", "Бесплатные и быстрые"),
    Category("reasoning", "Продвинутые рассуждения"),
    Category("image_gen", "Генерация изображений"),
)

MODELS: tuple[ModelInfo, ...] = (
    # --- Free and fast ---
    ModelInfo(
        "nvidia/nemotron-3.5-super-vl:free",
        "NVIDIA Nemotron 3.5 Super VL",
        "fast",
        supports_vision=True,
    ),
    ModelInfo("mimo/mimo-2.6-flash", "MiMo 2.6 Flash", "fast", 0.10, 0.30),
    ModelInfo("deepseek/deepseek-v4.1-flash", "DeepSeek V4.1", "fast", 0.14, 0.28),
    ModelInfo("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B", "fast", 0.35, 0.40),
    # --- Advanced reasoning ---
    ModelInfo("deepseek/deepseek-v4.1-reasoner", "DeepSeek V4.1 Reasoner", "reasoning", 0.55, 2.20),
    ModelInfo("dots-studio/dots3-note-preview:free", "Dots3 Note", "reasoning"),
    # --- Image generation ---
    ModelInfo(
        "black-forest-labs/flux-1-schnell",
        "FLUX.1 Schnell",
        "image_gen",
        price_image=0.003,
        supports_image_generation=True,
    ),
    ModelInfo(
        "stabilityai/stable-diffusion-3.5-large",
        "SD 3.5 Large",
        "image_gen",
        price_image=0.065,
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