"""Cost accounting for OpenRouter requests.

Prices are pulled from the OpenRouter ``/models`` endpoint (per-token USD),
cached in SQLite and in memory. When the provider reports the real cost in the
usage payload, that value is preferred over the estimate.
"""

from __future__ import annotations

import logging

from bot.database.db import Database
from bot.services.openrouter import OpenRouterClient, OpenRouterError

logger = logging.getLogger(__name__)

# OpenRouter pricing strings are USD per single token.
PRICE_SCALE = 1_000_000  # display per 1M tokens


def format_cost(amount: float) -> str:
    """Format a USD amount for display."""
    if amount <= 0:
        return "$0.00"
    if amount < 0.01:
        return f"${amount:.6f}"
    if amount < 1:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def format_price_per_million(per_token: float) -> str:
    """Format a per-token price as USD per 1M tokens."""
    return format_cost(per_token * PRICE_SCALE)


class PricingService:
    """Fetches, caches and applies OpenRouter model pricing."""

    def __init__(self, db: Database, client: OpenRouterClient) -> None:
        self._db = db
        self._client = client
        self._cache: dict[str, tuple[float, float, float]] = {}

    async def refresh(self) -> int:
        """Pull the model catalog and persist per-token prices.

        Returns the number of models whose pricing was stored.
        """
        models = await self._client.list_models()
        items: list[tuple[str, float, float, float]] = []
        for model in models:
            model_id = model.get("id")
            if not model_id:
                continue
            pricing = model.get("pricing") or {}

            def _to_float(key: str) -> float:
                try:
                    return float(pricing.get(key) or 0)
                except (TypeError, ValueError):
                    return 0.0

            items.append(
                (str(model_id), _to_float("prompt"), _to_float("completion"), _to_float("image"))
            )

        if items:
            await self._db.save_pricing(items)
            self._cache = {mid: (p, c, i) for mid, p, c, i in items}
            logger.info("Pricing refreshed for %d models", len(items))
        return len(items)

    async def ensure_loaded(self) -> None:
        """Load prices from DB, refreshing from OpenRouter when empty."""
        if self._cache:
            return
        self._cache = await self._db.get_pricing_all()
        if self._cache:
            return
        try:
            await self.refresh()
        except OpenRouterError as exc:
            logger.warning("Could not load pricing: %s", exc)

    async def get_price(self, model_id: str) -> tuple[float, float, float]:
        """Return ``(prompt, completion, image)`` prices for *model_id*."""
        await self.ensure_loaded()
        return self._cache.get(model_id, (0.0, 0.0, 0.0))

    async def estimate_cost(
        self,
        model_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        reported_cost: float | None = None,
    ) -> float:
        """Compute a chat request cost, preferring the provider-reported value."""
        if reported_cost is not None and reported_cost > 0:
            return reported_cost
        prompt_price, completion_price, _ = await self.get_price(model_id)
        return prompt_tokens * prompt_price + completion_tokens * completion_price

    async def estimate_image_cost(self, model_id: str, images: int, prompt_tokens: int) -> float:
        """Estimate the cost of an image generation request."""
        prompt_price, _, image_price = await self.get_price(model_id)
        return prompt_tokens * prompt_price + images * image_price

    async def last_updated(self) -> str | None:
        """When the price table was last refreshed."""
        return await self._db.get_pricing_updated_at()
