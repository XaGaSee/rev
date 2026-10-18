"""Typed records returned by the database layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class User:
    """A persisted bot user."""

    user_id: int
    username: str | None
    first_name: str | None
    model: str
    temperature: float
    system_prompt: str | None
    requests: int
    tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost: float
    budget: float
    daily_count: int
    daily_date: str | None
    created_at: str
    last_active: str

    @property
    def display_name(self) -> str:
        """Best-effort display name for greetings."""
        if self.first_name:
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return str(self.user_id)

    @property
    def budget_exceeded(self) -> bool:
        """Whether the user spent their whole budget (0 means unlimited)."""
        return self.budget > 0 and self.cost >= self.budget


@dataclass(slots=True)
class HistoryMessage:
    """A single dialog turn stored for context."""

    role: str
    content: str
    created_at: str


@dataclass(slots=True)
class Stats:
    """Aggregated bot statistics."""

    users: int
    requests: int
    tokens: int
    cost: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    active_today: int = 0
