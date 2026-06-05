"""Tests for random-triggered companion messaging."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from nanobot.companion.delivery import pick_delivery_target
from nanobot.companion.trigger import (
    companion_state_path,
    in_quiet_hours,
    record_companion_sent,
    should_send_companion_message,
)
from nanobot.config.schema import CompanionConfig


def test_in_quiet_hours_overnight_span():
    tz = ZoneInfo("Asia/Shanghai")
    assert in_quiet_hours(
        now=datetime(2026, 6, 4, 23, 30, tzinfo=tz),
        quiet_start="23:00",
        quiet_end="08:00",
    )
    assert in_quiet_hours(
        now=datetime(2026, 6, 4, 7, 0, tzinfo=tz),
        quiet_start="23:00",
        quiet_end="08:00",
    )
    assert not in_quiet_hours(
        now=datetime(2026, 6, 4, 12, 0, tzinfo=tz),
        quiet_start="23:00",
        quiet_end="08:00",
    )


def _utc_noon_ms(year: int = 2026, month: int = 6, day: int = 4) -> int:
    return int(datetime(year, month, day, 12, 0, tzinfo=ZoneInfo("UTC")).timestamp() * 1000)


def test_should_send_respects_min_interval(tmp_path: Path):
    cfg = CompanionConfig(
        enabled=True,
        send_probability=1.0,
        min_interval_s=3600,
        quiet_hours_start="23:00",
        quiet_hours_end="08:00",
    )
    state_path = companion_state_path(tmp_path)
    noon_ms = _utc_noon_ms()
    record_companion_sent(state_path, now_ms=noon_ms)

    decision = should_send_companion_message(
        cfg,
        workspace=tmp_path,
        timezone="UTC",
        rng=random.Random(0),
        now_ms=noon_ms + 30 * 60 * 1000,
    )
    assert decision.should_send is False
    assert "min interval" in decision.reason


def test_should_send_on_random_hit(tmp_path: Path):
    noon_ms = _utc_noon_ms()
    always = CompanionConfig(
        enabled=True,
        send_probability=1.0,
        min_interval_s=0,
    )
    never = CompanionConfig(
        enabled=True,
        send_probability=0.0,
        min_interval_s=0,
    )
    hit = should_send_companion_message(
        always,
        workspace=tmp_path,
        timezone="UTC",
        rng=random.Random(0),
        now_ms=noon_ms,
    )
    miss = should_send_companion_message(
        never,
        workspace=tmp_path,
        timezone="UTC",
        rng=random.Random(0),
        now_ms=noon_ms,
    )
    assert hit.should_send is True
    assert miss.should_send is False


def test_should_send_skips_recent_user_chat(tmp_path: Path):
    from datetime import datetime

    noon_ms = _utc_noon_ms()
    cfg = CompanionConfig(
        enabled=True,
        send_probability=1.0,
        min_interval_s=0,
        recent_chat_skip_minutes=30,
        channel="weixin",
        chat_id="user-1",
    )

    class _Sessions:
        def read_session_file(self, key: str):
            if key != "weixin:user-1":
                return None
            return {
                "updated_at": datetime.fromtimestamp(noon_ms / 1000 - 600).isoformat(),
            }

    decision = should_send_companion_message(
        cfg,
        workspace=tmp_path,
        timezone="UTC",
        rng=random.Random(0),
        now_ms=noon_ms,
        session_manager=_Sessions(),  # type: ignore[arg-type]
        delivery_channel="weixin",
        delivery_chat_id="user-1",
    )
    assert decision.should_send is False
    assert decision.reason == "recent user chat"


def test_pick_delivery_target_prefers_pin():
    class _Sessions:
        def list_sessions(self):
            return [{"key": "telegram:111"}]

    channel, chat_id = pick_delivery_target(
        pinned_channel="telegram",
        pinned_chat_id="999",
        enabled_channels={"telegram"},
        session_manager=_Sessions(),  # type: ignore[arg-type]
    )
    assert (channel, chat_id) == ("telegram", "999")


def test_pick_delivery_target_falls_back_to_session():
    class _Sessions:
        def list_sessions(self):
            return [{"key": "telegram:111"}]

    channel, chat_id = pick_delivery_target(
        pinned_channel="",
        pinned_chat_id="",
        enabled_channels={"telegram"},
        session_manager=_Sessions(),  # type: ignore[arg-type]
    )
    assert (channel, chat_id) == ("telegram", "111")
