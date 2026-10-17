"""Finite state machine states used across the handlers."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    """User configurability of the active model."""

    temperature = State()
    system_prompt = State()
    budget = State()


class ImageStates(StatesGroup):
    """Prompt collection for image generation."""

    prompt = State()


class ModelStates(StatesGroup):
    """Model catalog search flow."""

    WaitForModelSearch = State()


class AdminStates(StatesGroup):
    """Admin panel flows."""

    broadcast = State()
