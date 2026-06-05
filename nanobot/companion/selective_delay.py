"""Rule-based inbound reply delay for a more human chat rhythm."""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.companion.mood import MoodState
    from nanobot.config.schema import SelectiveDelayConfig

_DISMISSIVE = frozenset({"嗯", "嗯嗯", "哦", "好", "好的", "行", "ok", "OK", "噢", "恩", "收到", "好哒"})
_LAUGH = re.compile(r"^(哈+|hh+|lol)+$", re.I)


def should_apply_selective_delay(
    *,
    channel: str,
    cfg: SelectiveDelayConfig,
    is_command: bool = False,
    is_internal: bool = False,
) -> bool:
    if not cfg.enabled or is_command or is_internal:
        return False
    return channel in cfg.channels


def decide_inbound_delay_s(
    content: str,
    cfg: SelectiveDelayConfig,
    mood: MoodState | None,
    *,
    rng: random.Random | None = None,
) -> float:
    """Return seconds to wait before starting the agent turn (typing may already show)."""
    roll_rng = rng or random.Random()
    text = (content or "").strip()
    if not text:
        return 0.0

    normalized = text.rstrip("。.!！?？~～…")
    delay = 0.0

    if normalized in _DISMISSIVE or _LAUGH.match(normalized):
        if roll_rng.random() < cfg.casual_defer_probability:
            delay = roll_rng.uniform(cfg.long_delay_min_s, cfg.long_delay_max_s)
    elif len(normalized) <= 8 and "?" not in normalized and "？" not in normalized:
        if roll_rng.random() < cfg.low_stakes_probability:
            delay = roll_rng.uniform(cfg.min_delay_s, cfg.max_delay_s * 1.4)
    elif "?" in normalized or "？" in normalized or any(c in normalized for c in ("吗", "么", "嘛")):
        delay = roll_rng.uniform(cfg.min_delay_s * 0.5, cfg.max_delay_s * 0.85)
    else:
        if roll_rng.random() < 0.45:
            delay = roll_rng.uniform(cfg.min_delay_s, cfg.max_delay_s)

    if mood is not None:
        from nanobot.companion.mood import mood_delay_multiplier

        delay *= mood_delay_multiplier(mood)

    return max(0.0, delay)
