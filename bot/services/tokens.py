"""Token accounting helpers."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token for latin text)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list[dict]) -> int:
    """Estimate tokens for a list of chat messages."""
    total = 0
    for message in messages:
        content = message.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += estimate_tokens(part.get("text", ""))
                else:
                    total += 85  # rough cost of an image
    return total


def format_tokens(count: int) -> str:
    """Format a token number with thousands separator."""
    return f"{count:,}".replace(",", " ")


def fit_messages(messages: list[dict], max_tokens: int) -> list[dict]:
    """Trim *messages* to a sliding window of *max_tokens*.

    System messages are always preserved. Oldest non-system turns are removed
    (in pairs to keep the user/assistant alternation) while the estimate stays
    above the budget.
    """
    if max_tokens <= 0 or estimate_messages_tokens(messages) <= max_tokens:
        return list(messages)

    result = list(messages)
    while estimate_messages_tokens(result) > max_tokens:
        indices = [i for i, m in enumerate(result) if m.get("role") != "system"]
        if len(indices) <= 1:
            break
        remove = 2 if len(indices) >= 3 else 1
        for index in sorted(indices[:remove], reverse=True):
            result.pop(index)
    return result
