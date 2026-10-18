"""Tests for the model catalog (badges, search, capabilities)."""

from __future__ import annotations

from bot.data.catalog import (
    CATEGORIES,
    DEFAULT_MODEL_ID,
    DEFAULT_MODEL_INFO,
    MODELS,
    get_model,
    image_models,
    is_image_model,
    is_vision_model,
    models_by_category,
    search_models,
    vision_models,
)


def test_default_model_is_nemotron():
    assert DEFAULT_MODEL_ID == "nvidia/nemotron-3.5-super-vl:free"
    assert DEFAULT_MODEL_INFO.supports_vision
    assert DEFAULT_MODEL_INFO.label == "NVIDIA Nemotron 3.5 Super VL [Free]"


def test_price_badges():
    deepseek = get_model("deepseek/deepseek-v4.1-flash")
    assert deepseek.price_short == "[$0.14/$0.28]"
    assert get_model("dots-studio/dots3-note-preview:free").price_short == "[Free]"
    assert get_model("black-forest-labs/flux-1-schnell").price_short == "[$0.003]"


def test_unknown_model_falls_back_to_default():
    assert get_model("nonexistent/model-id") is DEFAULT_MODEL_INFO


def test_capabilities():
    assert is_vision_model("nvidia/nemotron-3.5-super-vl:free")
    assert not is_vision_model("deepseek/deepseek-v4.1-flash")
    assert is_image_model("black-forest-labs/flux-1-schnell")
    assert is_image_model("stabilityai/stable-diffusion-3.5-large")
    assert not is_image_model("qwen/qwen-3-vl")


def test_categories_are_non_empty():
    for category in CATEGORIES:
        assert models_by_category(category.key), category.key
    assert len(image_models()) == 2
    assert len(vision_models()) >= 1


def test_search_by_id_and_name():
    assert search_models("deepseek")  # id fragment
    assert search_models("flux")  # name fragment
    assert search_models("NVIDIA") == [DEFAULT_MODEL_INFO]
    assert search_models("zzz-no-match") == []
    assert search_models("  ") == []