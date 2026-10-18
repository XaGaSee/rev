"""Tests for shared UI payloads (main screen format, keyboards)."""

from __future__ import annotations

from bot.database.models import User
from bot.ui import get_main_menu_payload, get_models_payload, get_profile_payload


def make_user(**overrides) -> User:
    defaults = dict(
        user_id=1,
        username=None,
        first_name=None,
        model="nvidia/nemotron-3.5-super-vl:free",
        temperature=0.7,
        system_prompt=None,
        requests=0,
        tokens=0,
        prompt_tokens=0,
        completion_tokens=0,
        cost=0.0,
        budget=0.0,
        daily_count=3,
        daily_date="2026-10-18",
        created_at="x",
        last_active="x",
    )
    defaults.update(overrides)
    return User(**defaults)


def test_main_menu_text_format():
    text, kb = get_main_menu_payload(make_user(), 7, False)
    assert text.startswith("AI Gateway\n")
    assert "Модель: NVIDIA Nemotron 3.5 Super VL [Free]\n" in text
    assert "Лимит: 3 / 10 запросов (сброс в 00:00 UTC)" in text
    assert "Контекст: 7 сообщений" in text
    assert text.rstrip().endswith("Отправьте сообщение, фото или голосовую заметку.")
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert labels[:4] == ["Модели", "🔍 Поиск", "Сброс контекста", "Профиль и расход"]


def test_main_menu_plural_and_admin_unlimited():
    _, _ = get_main_menu_payload(make_user(), 0, False)
    text_one, _ = get_main_menu_payload(make_user(), 1, False)
    assert "Контекст: 1 сообщение" in text_one
    admin_text, admin_kb = get_main_menu_payload(make_user(), 5, True)
    assert "Лимит: без ограничений (администратор)" in admin_text
    assert "Админ-панель" in [btn.text for row in admin_kb.inline_keyboard for btn in row]


def test_main_menu_daily_rollover():
    user = make_user(daily_date="2026-10-17")  # stale date -> counter reset
    text, _ = get_main_menu_payload(user, 0, False)
    assert "Лимит: 0 / 10 запросов" in text


def test_profile_payload_has_settings_entry():
    text, kb = get_profile_payload(make_user())
    assert "Профиль" in text
    rows = [[btn.text for btn in row] for row in kb.inline_keyboard]
    assert ["Настройки"] in rows
    assert ["Назад"] in rows
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "menu:settings" in callbacks
    assert "menu:main" in callbacks


def test_models_payload():
    text, kb = get_models_payload()
    assert "Каталог моделей" in text
    assert any(btn.callback_data == "models:search" for r in kb.inline_keyboard for btn in r)