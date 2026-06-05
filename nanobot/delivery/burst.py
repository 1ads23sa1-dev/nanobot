"""Split outbound assistant text into multiple chat bubbles."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.companion.mood import MoodState
    from nanobot.config.schema import MessageBurstConfig

_SENTENCE_BREAK_RE = re.compile(r"(?<=[。！？!?…])\s*")

_HESITATION_OPENERS = ("嗯…", "那个…", "等等，", "啊，", "呃…")
_CORRECTION_PREFIXES = ("不对，", "我是说——", "打错了，是", "算了，其实是")


@dataclass(frozen=True)
class BurstDelivery:
    """Sequential chat bubbles and pauses between them."""

    parts: list[str]
    delays_after_s: list[float]

    def __post_init__(self) -> None:
        if len(self.delays_after_s) != max(0, len(self.parts) - 1):
            raise ValueError("delays_after_s must have len(parts)-1 entries")


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


def _stumble_delay_s(cfg: MessageBurstConfig, rng: random.Random) -> float:
    low = min(cfg.stumble_min_delay_s, cfg.stumble_max_delay_s)
    high = max(cfg.stumble_min_delay_s, cfg.stumble_max_delay_s)
    return rng.uniform(low, high) if low != high else low


def _apply_hesitation(parts: list[str], cfg: MessageBurstConfig, rng: random.Random) -> BurstDelivery:
    opener = rng.choice(_HESITATION_OPENERS)
    merged = [opener, *parts]
    delays = [_stumble_delay_s(cfg, rng)]
    delays.extend(random_burst_delay_s(cfg, rng=rng) for _ in range(len(parts) - 1))
    return BurstDelivery(merged, delays)


def _apply_correction(text: str, cfg: MessageBurstConfig, rng: random.Random) -> BurstDelivery | None:
    split = _smart_split_once(text)
    if len(split) < 2:
        return None
    prefix = rng.choice(_CORRECTION_PREFIXES)
    delays = [_stumble_delay_s(cfg, rng)]
    return BurstDelivery([split[0], f"{prefix}{split[1]}"], delays)


def apply_stumble(
    parts: list[str],
    full_text: str,
    cfg: MessageBurstConfig,
    *,
    rng: random.Random | None = None,
    mood: MoodState | None = None,
) -> BurstDelivery:
    """Maybe prepend hesitation or insert a correction bubble."""
    roll_rng = rng or random.Random()
    if not parts or not cfg.stumble_enabled:
        return _delivery_from_parts(parts, cfg, roll_rng)

    prob = cfg.stumble_probability
    if mood is not None:
        from nanobot.companion.mood import mood_stumble_multiplier

        prob = min(0.35, prob * mood_stumble_multiplier(mood))

    if roll_rng.random() >= prob:
        return _delivery_from_parts(parts, cfg, roll_rng)

    if len(parts) == 1:
        correction = _apply_correction(full_text, cfg, roll_rng)
        if correction is not None and roll_rng.random() < cfg.correction_weight:
            return correction
        return _apply_hesitation(parts, cfg, roll_rng)

    if roll_rng.random() < 0.7:
        return _apply_hesitation(parts, cfg, roll_rng)
    return _delivery_from_parts(parts, cfg, roll_rng)


def _delivery_from_parts(
    parts: list[str],
    cfg: MessageBurstConfig,
    rng: random.Random,
) -> BurstDelivery:
    if len(parts) <= 1:
        return BurstDelivery(parts, [])
    delays = [random_burst_delay_s(cfg, rng=rng) for _ in range(len(parts) - 1)]
    return BurstDelivery(parts, delays)


def plan_burst_delivery(
    content: str,
    cfg: MessageBurstConfig,
    *,
    rng: random.Random | None = None,
    mood: MoodState | None = None,
) -> BurstDelivery:
    """Plan burst parts, optional stumble, and inter-part delays."""
    roll_rng = rng or random.Random()
    text = (content or "").strip()
    if not text or not cfg.enabled:
        return BurstDelivery([text] if text else [], [])

    parts = maybe_burst_parts(text, cfg, rng=roll_rng)
    return apply_stumble(parts, text, cfg, rng=roll_rng, mood=mood)


def random_burst_delay_s(cfg: MessageBurstConfig, *, rng: random.Random | None = None) -> float:
    """Sample a human-like pause between burst parts."""
    roll_rng = rng or random.Random()
    low = min(cfg.min_delay_s, cfg.max_delay_s)
    high = max(cfg.min_delay_s, cfg.max_delay_s)
    if low == high:
        return low
    return roll_rng.uniform(low, high)
