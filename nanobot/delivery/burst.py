"""Split outbound assistant text into multiple chat bubbles."""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.config.schema import MessageBurstConfig

_SENTENCE_BREAK_RE = re.compile(r"(?<=[。！？!?…])\s*")


def _split_on_marker(content: str, marker: str, *, max_parts: int) -> list[str]:
    if not marker or marker not in content:
        return []
    parts = [part.strip() for part in content.split(marker) if part.strip()]
    if len(parts) <= 1:
        return []
    return parts[:max_parts]


def _smart_split_once(text: str) -> list[str]:
    """Split at the first strong sentence boundary when possible."""
    stripped = text.strip()
    if not stripped:
        return []
    matches = list(_SENTENCE_BREAK_RE.finditer(stripped))
    if not matches:
        return [stripped]
    # Prefer splitting near the middle for a natural two-bubble feel.
    mid = len(stripped) // 2
    best_idx = min(range(len(matches)), key=lambda i: abs(matches[i].end() - mid))
    cut = matches[best_idx].end()
    first = stripped[:cut].strip()
    second = stripped[cut:].strip()
    if not first or not second:
        return [stripped]
    return [first, second]


def maybe_burst_parts(
    content: str,
    cfg: MessageBurstConfig,
    *,
    rng: random.Random | None = None,
    force_burst: bool = False,
) -> list[str]:
    """Return one or more message parts for sequential delivery."""
    text = (content or "").strip()
    if not text or not cfg.enabled:
        return [text] if text else []

    marker_parts = _split_on_marker(text, cfg.split_marker, max_parts=cfg.max_parts)
    if marker_parts:
        return marker_parts

    roll_rng = rng or random.Random()
    if not force_burst and roll_rng.random() >= cfg.burst_probability:
        return [text]

    split = _smart_split_once(text)
    if len(split) <= 1:
        return [text]
    return split[: cfg.max_parts]


def random_burst_delay_s(cfg: MessageBurstConfig, *, rng: random.Random | None = None) -> float:
    """Sample a human-like pause between burst parts."""
    roll_rng = rng or random.Random()
    low = min(cfg.min_delay_s, cfg.max_delay_s)
    high = max(cfg.min_delay_s, cfg.max_delay_s)
    if low == high:
        return low
    return roll_rng.uniform(low, high)
