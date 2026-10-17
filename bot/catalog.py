"""Curated OpenRouter model catalog grouped by category."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class ModelInfo:
    """A single selectable model."""

    id: str
    name: str
    category: str
    description: str = ""
    vision: bool = False
    image_generation: bool = False

    @property
    def label(self) -> str:
        """Human friendly button label."""
        return f"{self.name}"


@dataclass(frozen=True)
class Category:
    """A model category."""

    key: str
    title: str
    icon: str


CATEGORIES: tuple[Category, ...] = (
    Category("fast", "Быстрые / Экономные", "🚀"),
    Category("reasoning", "Умные / Рассуждающие", "🧠"),
    Category("vision", "Анализ изображений", "👁️"),
    Category("image_gen", "Генерация графики", "🎨"),
)

CATEGORY_MAP: dict[str, Category] = {c.key: c for c in CATEGORIES}

MODELS: tuple[ModelInfo, ...] = (
    # --- Fast / cheap ---
    ModelInfo("openai/gpt-4o-mini", "GPT-4o mini", "fast", "Быстрая и дешёвая", vision=True),
    ModelInfo("google/gemini-2.0-flash-001", "Gemini 2.0 Flash", "fast", "Очень быстрая", vision=True),
    ModelInfo("meta-llama/llama-3.1-8b-instruct", "Llama 3.1 8B", "fast", "Лёгкая open source"),
    ModelInfo("mistralai/mistral-7b-instruct", "Mistral 7B", "fast", "Экономная"),
    ModelInfo("anthropic/claude-3-haiku", "Claude 3 Haiku", "fast", "Быстрая Claude"),
    ModelInfo("qwen/qwen-2.5-7b-instruct", "Qwen 2.5 7B", "fast", "Мультиязычная"),
    # --- Reasoning ---
    ModelInfo("openai/gpt-4o", "GPT-4o", "reasoning", "Флагман OpenAI", vision=True),
    ModelInfo("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet", "reasoning", "Сильный reasoning", vision=True),
    ModelInfo("openai/o1-mini", "o1-mini", "reasoning", "Пошаговые рассуждения"),
    ModelInfo("deepseek/deepseek-r1", "DeepSeek R1", "reasoning", "Открытая reasoning модель"),
    ModelInfo("meta-llama/llama-3.1-70b-instruct", "Llama 3.1 70B", "reasoning", "Крупная open source"),
    # --- Vision ---
    ModelInfo("openai/gpt-4o", "GPT-4o Vision", "vision", "Изображения + текст", vision=True),
    ModelInfo("google/gemini-2.0-flash-001", "Gemini Flash Vision", "vision", "Быстрый vision", vision=True),
    ModelInfo("anthropic/claude-3.5-sonnet", "Claude 3.5 Vision", "vision", "Детальный анализ", vision=True),
    ModelInfo("qwen/qwen-2.5-vl-72b-instruct", "Qwen2.5-VL 72B", "vision", "Открытый vision", vision=True),
    # --- Image generation ---
    ModelInfo(
        "google/gemini-2.5-flash-image-preview",
        "Gemini Image (Nano Banana)",
        "image_gen",
        "Генерация и редактирование изображений",
        image_generation=True,
    ),
)

MODEL_MAP: dict[str, ModelInfo] = {m.id: m for m in MODELS}
DEFAULT_MODEL_INFO: ModelInfo = MODEL_MAP.get("openai/gpt-4o-mini", MODELS[0])


def models_by_category(category: str) -> list[ModelInfo]:
    """Return all models belonging to *category*."""
    return [m for m in MODELS if m.category == category]


def get_model(model_id: str) -> ModelInfo:
    """Return :class:`ModelInfo` for *model_id* or the default model."""
    return MODEL_MAP.get(model_id, DEFAULT_MODEL_INFO)


def is_image_model(model_id: str) -> bool:
    """Whether *model_id* generates images instead of text."""
    return get_model(model_id).image_generation


def is_vision_model(model_id: str) -> bool:
    """Whether *model_id* accepts image inputs."""
    return get_model(model_id).vision


def iter_models() -> Iterable[ModelInfo]:
    """Iterate over every catalogued model."""
    return iter(MODELS)
