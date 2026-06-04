"""Random-trigger logic for proactive companion messages."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from nanobot.config.schema import CompanionConfig


@dataclass(frozen=True)
class CompanionTriggerDecision:
    """Outcome of a companion send roll."""

    should_send: bool
    reason: str


def companion_state_path(workspace: Path) -> Path:
    return workspace / ".companion_state.json"


def read_companion_state(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record_companion_sent(path: Path, *, now_ms: int | None = None) -> None:
    timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_sent_ms": timestamp}, indent=2) + "\n",
        encoding="utf-8",
    )


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    text = (value or "").strip()
    if not text or ":" not in text:
        return None
    hour_text, minute_text = text.split(":", 1)
    try:
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def in_quiet_hours(
    *,
    now: datetime,
    quiet_start: str,
    quiet_end: str,
) -> bool:
    """Return True when *now* falls inside the quiet window (supports overnight spans)."""
    start = _parse_hhmm(quiet_start)
    end = _parse_hhmm(quiet_end)
    if start is None or end is None:
        return False

    start_minutes = start[0] * 60 + start[1]
    end_minutes = end[0] * 60 + end[1]
    current_minutes = now.hour * 60 + now.minute

    if start_minutes == end_minutes:
        return False
    if start_minutes < end_minutes:
        return start_minutes <= current_minutes < end_minutes
    return current_minutes >= start_minutes or current_minutes < end_minutes


def should_send_companion_message(
    cfg: CompanionConfig,
    *,
    workspace: Path,
    timezone: str,
    rng: random.Random | None = None,
    now_ms: int | None = None,
) -> CompanionTriggerDecision:
    """Decide whether this companion check should send a proactive message."""
    if not cfg.enabled:
        return CompanionTriggerDecision(False, "companion disabled")

    timestamp_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    try:
        now_local = datetime.fromtimestamp(timestamp_ms / 1000, tz=ZoneInfo(timezone))
    except Exception:
        now_local = datetime.fromtimestamp(timestamp_ms / 1000).astimezone()

    if in_quiet_hours(
        now=now_local,
        quiet_start=cfg.quiet_hours_start,
        quiet_end=cfg.quiet_hours_end,
    ):
        return CompanionTriggerDecision(False, "quiet hours")

    state = read_companion_state(companion_state_path(workspace))
    last_sent_ms = state.get("last_sent_ms")
    if isinstance(last_sent_ms, int) and cfg.min_interval_s > 0:
        elapsed_s = (timestamp_ms - last_sent_ms) / 1000
        if elapsed_s < cfg.min_interval_s:
            return CompanionTriggerDecision(
                False,
                f"min interval ({int(elapsed_s)}s < {cfg.min_interval_s}s)",
            )

    roll = (rng or random.Random()).random()
    if roll >= cfg.send_probability:
        return CompanionTriggerDecision(
            False,
            f"random miss (roll={roll:.4f}, p={cfg.send_probability})",
        )

    return CompanionTriggerDecision(True, f"random hit (roll={roll:.4f}, p={cfg.send_probability})")
