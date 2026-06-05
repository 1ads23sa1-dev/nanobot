"""Tests for companion mood state."""

from __future__ import annotations

from pathlib import Path

from nanobot.companion.mood import (
    MoodState,
    decay_mood,
    load_mood,
    mood_runtime_line,
    on_user_message,
    save_mood,
    touch_mood_for_chat,
)


def test_warm_user_message_increases_warmth():
    base = MoodState(warmth=0.5, worry=0.3, updated_ms=1)
    updated = on_user_message(base, "谢谢你呀，想你", now_ms=2)
    assert updated.warmth > base.warmth
    assert updated.worry < base.worry


def test_dismissive_message_increases_prickly():
    base = MoodState(prickly=0.2, updated_ms=1)
    updated = on_user_message(base, "嗯", now_ms=2)
    assert updated.prickly > base.prickly


def test_mood_persists_per_chat(tmp_path: Path):
    touch_mood_for_chat(
        tmp_path,
        "weixin",
        "u1",
        user_content="好开心",
    )
    loaded = load_mood(tmp_path, "weixin", "u1")
    assert loaded.warmth > 0.55


def test_decay_moves_toward_baseline():
    hot = MoodState(warmth=0.95, worry=0.8, prickly=0.7, updated_ms=0)
    cooled = decay_mood(hot, now_ms=8 * 3_600_000, half_life_hours=8.0)
    assert cooled.warmth < hot.warmth
    assert cooled.worry < hot.worry


def test_runtime_line_not_empty():
    line = mood_runtime_line(MoodState(worry=0.7, warmth=0.8))
    assert "小祥" in line
