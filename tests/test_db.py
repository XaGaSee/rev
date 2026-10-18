"""Async database tests: upsert, daily limits, billing counters, history."""

from __future__ import annotations

from bot.data.catalog import DEFAULT_MODEL_ID
from bot.database.db import Database


async def make_db(tmp_path) -> Database:
    db = Database(str(tmp_path / "test.db"))
    await db.connect()
    return db


async def test_upsert_is_atomic(tmp_path):
    db = await make_db(tmp_path)
    u1 = await db.get_or_create_user(42, "old", "Old", DEFAULT_MODEL_ID, 0.7)
    u2 = await db.get_or_create_user(42, "new", "New", DEFAULT_MODEL_ID, 0.7)
    assert u2.username == "new"  # identity fields updated
    assert u2.model == u1.model == DEFAULT_MODEL_ID  # settings preserved
    assert u2.daily_count == 0
    await db.close()


async def test_daily_limit_consumption_and_rollover(tmp_path):
    db = await make_db(tmp_path)
    await db.get_or_create_user(7, None, None, DEFAULT_MODEL_ID, 0.7)
    ok1, used1 = await db.consume_daily_message(7, 2)
    ok2, used2 = await db.consume_daily_message(7, 2)
    ok3, used3 = await db.consume_daily_message(7, 2)
    assert (ok1, used1) == (True, 1)
    assert (ok2, used2) == (True, 2)
    assert (ok3, used3) == (False, 2)
    # admin reset frees the window again
    assert await db.reset_daily_limit(7)
    ok4, used4 = await db.consume_daily_message(7, 2)
    assert (ok4, used4) == (True, 1)
    await db.close()


async def test_billing_counters_separated(tmp_path):
    db = await make_db(tmp_path)
    await db.get_or_create_user(9, None, None, DEFAULT_MODEL_ID, 0.7)
    await db.increment_usage(
        9, requests=1, tokens=1500, prompt_tokens=1000, completion_tokens=500, cost=0.00028
    )
    user = await db.get_user(9)
    assert user.requests == 1
    assert user.prompt_tokens == 1000
    assert user.completion_tokens == 500
    assert user.tokens == 1500
    assert abs(user.cost - 0.00028) < 1e-12
    await db.close()


async def test_history_roundtrip_and_clear(tmp_path):
    db = await make_db(tmp_path)
    await db.get_or_create_user(11, None, None, DEFAULT_MODEL_ID, 0.7)
    await db.add_message(11, "user", "вопрос")
    await db.add_message(11, "assistant", "ответ")
    history = await db.get_history(11, 10)
    assert [m.role for m in history] == ["user", "assistant"]
    assert history[0].content == "вопрос"
    assert await db.count_messages(11) == 2
    removed = await db.clear_history(11)
    assert removed == 2
    assert await db.count_messages(11) == 0
    await db.close()


async def test_pricing_cache_roundtrip(tmp_path):
    db = await make_db(tmp_path)
    await db.save_pricing([("model-a", 0.14 / 1e6, 0.28 / 1e6, 0.0)])
    prices = await db.get_pricing_all()
    assert prices["model-a"] == (0.14 / 1e6, 0.28 / 1e6, 0.0)
    assert await db.get_pricing_updated_at() is not None
    await db.close()