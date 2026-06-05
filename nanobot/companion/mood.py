"""Persistent companion mood state per chat."""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from nanobot.companion.trigger import companion_state_path, in_quiet_hours, read_companion_state

_CHAT_KEY_RE = re.compile(r"[^\w:.-]+")
_WARM_WORDS = ("谢谢", "想你", "喜欢", "开心", "哈哈", "抱抱", "辛苦", "爱你", "乖")
_COLD_WORDS = ("别烦", "闭嘴", "滚", "无聊", "算了", "不想聊")
_DISMISSIVE = frozenset({"嗯", "嗯嗯", "哦", "好", "好的", "行", "ok", "OK", "噢", "恩"})


@dataclass
class MoodState:
    """0–1 axes; higher = more of that quality."""

    warmth: float = 0.55
    worry: float = 0.20
    energy: float = 0.60
    prickly: float = 0.15
    updated_ms: int = 0

    def clamp(self) -> MoodState:
        def _c(v: float) -> float:
            return max(0.0, min(1.0, v))

        return MoodState(
            warmth=_c(self.warmth),
            worry=_c(self.worry),
            energy=_c(self.energy),
            prickly=_c(self.prickly),
            updated_ms=self.updated_ms,
        )


def _chat_key(channel: str, chat_id: str) -> str:
    raw = f"{channel}:{chat_id}"
    return _CHAT_KEY_RE.sub("_", raw)


def _load_mood_map(path: Path) -> dict[str, Any]:
    state = read_companion_state(path)
    moods = state.get("moods")
    return moods if isinstance(moods, dict) else {}


def _write_mood_map(path: Path, moods: dict[str, Any]) -> None:
    state = read_companion_state(path)
    state["moods"] = moods
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_mood(workspace: Path, channel: str, chat_id: str) -> MoodState:
    path = companion_state_path(workspace)
    moods = _load_mood_map(path)
    raw = moods.get(_chat_key(channel, chat_id))
    if not isinstance(raw, dict):
        return MoodState(updated_ms=int(time.time() * 1000))
    try:
        return MoodState(
            warmth=float(raw.get("warmth", 0.55)),
            worry=float(raw.get("worry", 0.20)),
            energy=float(raw.get("energy", 0.60)),
            prickly=float(raw.get("prickly", 0.15)),
            updated_ms=int(raw.get("updated_ms") or time.time() * 1000),
        ).clamp()
    except (TypeError, ValueError):
        return MoodState(updated_ms=int(time.time() * 1000))


def save_mood(workspace: Path, channel: str, chat_id: str, mood: MoodState) -> None:
    path = companion_state_path(workspace)
    moods = _load_mood_map(path)
    key = _chat_key(channel, chat_id)
    stamped = mood.clamp()
    moods[key] = {
        "warmth": stamped.warmth,
        "worry": stamped.worry,
        "energy": stamped.energy,
        "prickly": stamped.prickly,
        "updated_ms": stamped.updated_ms,
    }
    _write_mood_map(path, moods)


def decay_mood(
    mood: MoodState,
    *,
    now_ms: int | None = None,
    half_life_hours: float = 8.0,
    timezone: str = "Asia/Shanghai",
    quiet_start: str = "23:00",
    quiet_end: str = "08:00",
) -> MoodState:
    """Drift mood axes toward neutral baselines over elapsed time."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    if mood.updated_ms <= 0:
        effective_ms = now - int(max(0.5, half_life_hours) * 3_600_000)
    else:
        effective_ms = mood.updated_ms

    elapsed_h = max(0.0, (now - effective_ms) / 3_600_000)
    if elapsed_h <= 0:
        return replace_updated(mood, now)

    factor = 0.5 ** (elapsed_h / max(0.5, half_life_hours))
    baseline = MoodState(updated_ms=now)
    try:
        now_local = datetime.fromtimestamp(now / 1000, tz=ZoneInfo(timezone))
    except Exception:
        now_local = datetime.fromtimestamp(now / 1000).astimezone()

    energy = baseline.energy + (mood.energy - baseline.energy) * factor
    if in_quiet_hours(now=now_local, quiet_start=quiet_start, quiet_end=quiet_end):
        energy = min(energy, 0.45)

    return MoodState(
        warmth=baseline.warmth + (mood.warmth - baseline.warmth) * factor,
        worry=baseline.worry + (mood.worry - baseline.worry) * factor,
        energy=energy,
        prickly=baseline.prickly + (mood.prickly - baseline.prickly) * factor,
        updated_ms=now,
    ).clamp()


def replace_updated(mood: MoodState, now_ms: int) -> MoodState:
    return MoodState(
        warmth=mood.warmth,
        worry=mood.worry,
        energy=mood.energy,
        prickly=mood.prickly,
        updated_ms=now_ms,
    )


def on_user_message(mood: MoodState, content: str, *, now_ms: int | None = None) -> MoodState:
    """Adjust mood from an inbound user message."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    text = (content or "").strip()
    warmth, worry, energy, prickly = mood.warmth, mood.worry, mood.energy, mood.prickly

    if text in _DISMISSIVE or (len(text) <= 4 and "?" not in text and "？" not in text):
        prickly = min(1.0, prickly + 0.06)
        warmth = max(0.0, warmth - 0.03)
    if any(w in text for w in _WARM_WORDS):
        warmth = min(1.0, warmth + 0.12)
        worry = max(0.0, worry - 0.08)
        prickly = max(0.0, prickly - 0.05)
    if any(w in text for w in _COLD_WORDS):
        prickly = min(1.0, prickly + 0.15)
        warmth = max(0.0, warmth - 0.10)
    if "?" in text or "？" in text or any(w in text for w in ("吗", "么", "嘛", "呢")):
        worry = min(1.0, worry + 0.04)

    return MoodState(warmth, worry, energy, prickly, now).clamp()


def on_bot_sent(mood: MoodState, content: str, *, now_ms: int | None = None) -> MoodState:
    """Adjust mood after the bot sends a visible reply."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    text = (content or "").strip()
    worry = mood.worry
    warmth = mood.warmth
    if any(w in text for w in ("?", "？", "吗", "么", "嘛", "呢", "担心", "没事吧")):
        worry = min(1.0, worry + 0.05)
    if any(w in text for w in _WARM_WORDS):
        warmth = min(1.0, warmth + 0.03)
    return MoodState(mood.warmth, worry, mood.energy, mood.prickly, now).clamp()


def on_user_silent_hours(mood: MoodState, hours: float, *, now_ms: int | None = None) -> MoodState:
    """Bump worry when the user has not replied for a while."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    if hours < 1:
        return replace_updated(mood, now)
    bump = min(0.25, 0.04 * math.log1p(hours))
    return MoodState(
        mood.warmth,
        min(1.0, mood.worry + bump),
        mood.energy,
        mood.prickly,
        now,
    ).clamp()


def mood_runtime_line(mood: MoodState) -> str:
    """One-line persona hint for the model (runtime metadata, not user-visible)."""
    traits: list[str] = []
    if mood.warmth >= 0.72:
        traits.append("语气偏软、愿意多关心对方")
    elif mood.warmth <= 0.35:
        traits.append("语气略收、不会太黏")
    if mood.worry >= 0.55:
        traits.append("有点担心对方、可轻轻追问")
    elif mood.worry <= 0.15:
        traits.append("不太焦虑、别过度追问")
    if mood.energy <= 0.35:
        traits.append("精力偏低、回复宜短")
    elif mood.energy >= 0.75:
        traits.append("状态尚可、可稍微活泼")
    if mood.prickly >= 0.55:
        traits.append("带一点刺、但底牌仍是关心")
    if not traits:
        traits.append("自然日常语气即可")
    return f"[小祥此刻状态：{'；'.join(traits)}]"


def mood_delay_multiplier(mood: MoodState) -> float:
    """Scale inbound selective delay — low energy / high prickly => slower."""
    mult = 1.0
    if mood.energy < 0.4:
        mult += (0.4 - mood.energy) * 1.2
    if mood.prickly > 0.5:
        mult += (mood.prickly - 0.5) * 0.8
    if mood.warmth > 0.7:
        mult -= 0.08
    return max(0.6, min(2.0, mult))


def mood_stumble_multiplier(mood: MoodState) -> float:
    """Scale stumble probability — worried/warm => more hesitation bubbles."""
    mult = 1.0 + mood.worry * 0.35 + mood.warmth * 0.15 - mood.prickly * 0.2
    return max(0.5, min(1.8, mult))


def touch_mood_for_chat(
    workspace: Path,
    channel: str,
    chat_id: str,
    *,
    user_content: str | None = None,
    bot_content: str | None = None,
    timezone: str = "Asia/Shanghai",
    quiet_start: str = "23:00",
    quiet_end: str = "08:00",
    half_life_hours: float = 8.0,
) -> MoodState:
    """Load, decay, apply event, save — convenience for hooks."""
    mood = load_mood(workspace, channel, chat_id)
    mood = decay_mood(
        mood,
        timezone=timezone,
        quiet_start=quiet_start,
        quiet_end=quiet_end,
        half_life_hours=half_life_hours,
    )
    if user_content is not None:
        mood = on_user_message(mood, user_content)
    if bot_content is not None:
        mood = on_bot_sent(mood, bot_content)
    save_mood(workspace, channel, chat_id, mood)
    logger.debug(
        "Mood {}:{} warmth={:.2f} worry={:.2f} energy={:.2f} prickly={:.2f}",
        channel,
        chat_id,
        mood.warmth,
        mood.worry,
        mood.energy,
        mood.prickly,
    )
    return mood
