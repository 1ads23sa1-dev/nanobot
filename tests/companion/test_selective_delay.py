"""Tests for selective inbound reply delay."""

from __future__ import annotations

import random

from nanobot.companion.mood import MoodState
from nanobot.companion.selective_delay import decide_inbound_delay_s, should_apply_selective_delay
from nanobot.config.schema import SelectiveDelayConfig


def test_casual_message_can_long_delay():
    cfg = SelectiveDelayConfig(casual_defer_probability=1.0)
    delay = decide_inbound_delay_s("好的", cfg, None, rng=random.Random(0))
    assert delay >= cfg.long_delay_min_s


def test_weixin_only_gate():
    cfg = SelectiveDelayConfig(enabled=True, channels=["weixin"])
    assert should_apply_selective_delay(channel="weixin", cfg=cfg)
    assert not should_apply_selective_delay(channel="telegram", cfg=cfg)


def test_low_energy_mood_slows_reply():
    cfg = SelectiveDelayConfig(casual_defer_probability=0.0, low_stakes_probability=1.0)
    low = MoodState(energy=0.2)
    normal = MoodState(energy=0.8)
    d_low = decide_inbound_delay_s("今天还行", cfg, low, rng=random.Random(1))
    d_norm = decide_inbound_delay_s("今天还行", cfg, normal, rng=random.Random(1))
    assert d_low >= d_norm
