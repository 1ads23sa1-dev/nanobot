"""Tests for outbound message burst splitting."""

from __future__ import annotations

import random

from nanobot.config.schema import MessageBurstConfig
from nanobot.delivery.burst import maybe_burst_parts, random_burst_delay_s


def test_honors_explicit_split_marker():
    cfg = MessageBurstConfig(burst_probability=0.0)
    parts = maybe_burst_parts("你好。\n---\n在吗？", cfg)
    assert parts == ["你好。", "在吗？"]


def test_random_burst_splits_at_sentence_boundary():
    cfg = MessageBurstConfig(burst_probability=1.0, max_parts=2)
    text = "今天天气不错。你那边怎么样？"
    parts = maybe_burst_parts(text, cfg, rng=random.Random(0))
    assert len(parts) == 2
    assert "".join(parts).replace(" ", "") == text.replace(" ", "")


def test_random_miss_returns_single_part():
    cfg = MessageBurstConfig(burst_probability=0.0)
    text = "就一句。"
    assert maybe_burst_parts(text, cfg, rng=random.Random(0)) == [text]


def test_random_burst_delay_within_bounds():
    cfg = MessageBurstConfig(min_delay_s=2.0, max_delay_s=5.0)
    rng = random.Random(42)
    for _ in range(20):
        delay = random_burst_delay_s(cfg, rng=rng)
        assert 2.0 <= delay <= 5.0
