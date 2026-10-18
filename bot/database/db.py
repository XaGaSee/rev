"""Async SQLite persistence built on top of ``aiosqlite``."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from bot.database.models import HistoryMessage, Stats, User

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT,
    first_name    TEXT,
    model         TEXT    NOT NULL,
    temperature   REAL    NOT NULL DEFAULT 0.7,
    system_prompt TEXT,
    requests        INTEGER NOT NULL DEFAULT 0,
    tokens          INTEGER NOT NULL DEFAULT 0,
    prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost            REAL    NOT NULL DEFAULT 0,
    budget          REAL    NOT NULL DEFAULT 0,
    daily_count     INTEGER NOT NULL DEFAULT 0,
    daily_date      TEXT,
    created_at      TEXT    NOT NULL,
    last_active     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    role       TEXT    NOT NULL,
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pricing (
    model_id   TEXT PRIMARY KEY,
    prompt     REAL NOT NULL DEFAULT 0,
    completion REAL NOT NULL DEFAULT 0,
    image      REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_user ON messages (user_id, id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def utc_today() -> str:
    """Current UTC date (daily counters roll over at midnight UTC)."""
    return datetime.now(timezone.utc).date().isoformat()


def _today() -> str:
    return utc_today()


class Database:
    """Thin async wrapper around a single SQLite connection."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._conn

    async def connect(self) -> None:
        """Open the connection and create the schema."""
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()
        await self._migrate()
        logger.info("Database connected: %s", self._path)

    async def _migrate(self) -> None:
        """Add columns introduced after the initial schema (idempotent)."""
        cursor = await self.connection.execute("PRAGMA table_info(users)")
        columns = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
        additions = {
            "cost": "ALTER TABLE users ADD COLUMN cost REAL NOT NULL DEFAULT 0",
            "budget": "ALTER TABLE users ADD COLUMN budget REAL NOT NULL DEFAULT 0",
            "prompt_tokens": "ALTER TABLE users ADD COLUMN prompt_tokens INTEGER NOT NULL DEFAULT 0",
            "completion_tokens": "ALTER TABLE users ADD COLUMN completion_tokens INTEGER NOT NULL DEFAULT 0",
            "daily_count": "ALTER TABLE users ADD COLUMN daily_count INTEGER NOT NULL DEFAULT 0",
            "daily_date": "ALTER TABLE users ADD COLUMN daily_date TEXT",
        }
        for column, statement in additions.items():
            if column not in columns:
                await self.connection.execute(statement)

        cursor = await self.connection.execute("PRAGMA table_info(pricing)")
        pricing_columns = {row["name"] for row in await cursor.fetchall()}
        await cursor.close()
        if pricing_columns and "image" not in pricing_columns:
            await self.connection.execute(
                "ALTER TABLE pricing ADD COLUMN image REAL NOT NULL DEFAULT 0"
            )
        await self.connection.commit()

    async def close(self) -> None:
        """Close the connection if it is open."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    # ------------------------------------------------------------------ users
    async def get_or_create_user(
        self,
        user_id: int,
        username: str | None,
        first_name: str | None,
        default_model: str,
        default_temperature: float,
    ) -> User:
        """Fetch a user or insert a fresh row."""
        row = await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if row is None:
            now = _now()
            await self.connection.execute(
                """
                INSERT INTO users
                    (user_id, username, first_name, model, temperature,
                     system_prompt, requests, tokens, created_at, last_active)
                VALUES (?, ?, ?, ?, ?, NULL, 0, 0, ?, ?)
                """,
                (user_id, username, first_name, default_model, default_temperature, now, now),
            )
            await self.connection.commit()
            row = await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        else:
            await self.connection.execute(
                "UPDATE users SET username = ?, first_name = ?, last_active = ? WHERE user_id = ?",
                (username, first_name, _now(), user_id),
            )
            await self.connection.commit()
            row = await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        assert row is not None
        return self._to_user(row)

    async def get_user(self, user_id: int) -> User | None:
        """Return a user or ``None``."""
        row = await self._fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self._to_user(row) if row else None

    async def set_model(self, user_id: int, model: str) -> None:
        await self._execute("UPDATE users SET model = ? WHERE user_id = ?", (model, user_id))

    async def set_temperature(self, user_id: int, temperature: float) -> None:
        await self._execute(
            "UPDATE users SET temperature = ? WHERE user_id = ?", (temperature, user_id)
        )

    async def set_system_prompt(self, user_id: int, prompt: str | None) -> None:
        await self._execute(
            "UPDATE users SET system_prompt = ? WHERE user_id = ?", (prompt, user_id)
        )

    async def increment_usage(
        self,
        user_id: int,
        requests: int = 1,
        tokens: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        """Increase request/token counters (in/out separately) and spend."""
        await self._execute(
            "UPDATE users SET requests = requests + ?, tokens = tokens + ?, "
            "prompt_tokens = prompt_tokens + ?, completion_tokens = completion_tokens + ?, "
            "cost = cost + ? WHERE user_id = ?",
            (requests, tokens, prompt_tokens, completion_tokens, cost, user_id),
        )

    # ------------------------------------------------------------ daily limit
    async def has_daily_quota(self, user_id: int, limit: int) -> bool:
        """Peek at the daily window without consuming a slot."""
        row = await self._fetchone(
            "SELECT daily_count, daily_date FROM users WHERE user_id = ?", (user_id,)
        )
        if row is None:
            return True
        if row["daily_date"] != _today():
            return True
        return int(row["daily_count"] or 0) < limit

    async def consume_daily_message(self, user_id: int, limit: int) -> tuple[bool, int]:
        """Register one generation against the UTC daily window.

        Returns ``(allowed, used_today)``; the counter rolls over at midnight UTC.
        """
        today = _today()
        row = await self._fetchone(
            "SELECT daily_count, daily_date FROM users WHERE user_id = ?", (user_id,)
        )
        if row is None:
            return True, 0
        count = int(row["daily_count"] or 0)
        if row["daily_date"] != today:
            count = 0
        if count >= limit:
            if row["daily_date"] != today:
                await self._execute(
                    "UPDATE users SET daily_date = ? WHERE user_id = ?", (today, user_id)
                )
            return False, count
        count += 1
        await self._execute(
            "UPDATE users SET daily_count = ?, daily_date = ? WHERE user_id = ?",
            (count, today, user_id),
        )
        return True, count

    async def reset_daily_limit(self, user_id: int) -> bool:
        """Zero out the daily counter for a user (admin action)."""
        cursor = await self.connection.execute(
            "UPDATE users SET daily_count = 0, daily_date = ? WHERE user_id = ?",
            (_today(), user_id),
        )
        await self.connection.commit()
        return bool(cursor.rowcount)

    async def count_active_today(self) -> int:
        """Number of users who generated at least one message today (UTC)."""
        row = await self._fetchone(
            "SELECT COUNT(*) AS n FROM users WHERE daily_date = ? AND daily_count > 0",
            (_today(),),
        )
        return int(row["n"]) if row else 0

    async def set_budget(self, user_id: int, amount: float) -> None:
        """Set a user's spend limit in USD (0 means unlimited)."""
        await self._execute(
            "UPDATE users SET budget = ? WHERE user_id = ?", (amount, user_id)
        )

    # ---------------------------------------------------------------- pricing
    async def save_pricing(self, items: list[tuple[str, float, float, float]]) -> None:
        """Bulk upsert ``(model_id, prompt, completion, image)`` rows."""
        if not items:
            return
        now = _now()
        await self.connection.executemany(
            """
            INSERT INTO pricing (model_id, prompt, completion, image, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(model_id) DO UPDATE SET
                prompt = excluded.prompt,
                completion = excluded.completion,
                image = excluded.image,
                updated_at = excluded.updated_at
            """,
            [
                (model_id, prompt, completion, image, now)
                for model_id, prompt, completion, image in items
            ],
        )
        await self.connection.commit()

    async def get_pricing_all(self) -> dict[str, tuple[float, float, float]]:
        """Return the whole cached price table."""
        rows = await self._fetchall("SELECT model_id, prompt, completion, image FROM pricing")
        return {
            row["model_id"]: (
                float(row["prompt"]),
                float(row["completion"]),
                float(row["image"]),
            )
            for row in rows
        }

    async def get_pricing_updated_at(self) -> str | None:
        """Return the timestamp of the most recent pricing refresh."""
        row = await self._fetchone("SELECT MAX(updated_at) AS ts FROM pricing")
        return row["ts"] if row and row["ts"] else None

    # --------------------------------------------------------------- messages
    async def add_message(self, user_id: int, role: str, content: str) -> None:
        """Persist a single dialog turn."""
        await self._execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, _now()),
        )

    async def get_history(self, user_id: int, limit: int) -> list[HistoryMessage]:
        """Return the most recent *limit* turns in chronological order."""
        rows = await self._fetchall(
            """
            SELECT role, content, created_at FROM (
                SELECT role, content, created_at, id
                FROM messages WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (user_id, limit),
        )
        return [
            HistoryMessage(
                role=row["role"], content=row["content"], created_at=row["created_at"]
            )
            for row in rows
        ]

    async def clear_history(self, user_id: int) -> int:
        """Delete all turns for a user, returning the number removed."""
        cursor = await self.connection.execute(
            "DELETE FROM messages WHERE user_id = ?", (user_id,)
        )
        await self.connection.commit()
        return cursor.rowcount or 0

    # ------------------------------------------------------------------ stats
    async def get_stats(self) -> Stats:
        """Return global aggregated statistics."""
        row = await self._fetchone(
            "SELECT COUNT(*) AS users, COALESCE(SUM(requests), 0) AS requests, "
            "COALESCE(SUM(tokens), 0) AS tokens, COALESCE(SUM(cost), 0) AS cost, "
            "COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens), 0) AS completion_tokens "
            "FROM users"
        )
        active = await self.count_active_today()
        if row is None:
            return Stats(
                users=0, requests=0, tokens=0, cost=0.0,
                prompt_tokens=0, completion_tokens=0, active_today=active,
            )
        return Stats(
            users=row["users"],
            requests=row["requests"],
            tokens=row["tokens"],
            cost=float(row["cost"]),
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            active_today=active,
        )

    async def all_user_ids(self) -> list[int]:
        """Return every known user id (for broadcasts)."""
        rows = await self._fetchall("SELECT user_id FROM users")
        return [row["user_id"] for row in rows]

    # --------------------------------------------------------------- internal
    async def _execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        await self.connection.execute(query, params)
        await self.connection.commit()

    async def _fetchone(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> aiosqlite.Row | None:
        cursor = await self.connection.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def _fetchall(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> list[aiosqlite.Row]:
        cursor = await self.connection.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return list(rows)

    @staticmethod
    def _to_user(row: aiosqlite.Row) -> User:
        return User(
            user_id=row["user_id"],
            username=row["username"],
            first_name=row["first_name"],
            model=row["model"],
            temperature=row["temperature"],
            system_prompt=row["system_prompt"],
            requests=row["requests"],
            tokens=row["tokens"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            cost=float(row["cost"]),
            budget=float(row["budget"]),
            daily_count=row["daily_count"],
            daily_date=row["daily_date"],
            created_at=row["created_at"],
            last_active=row["last_active"],
        )
