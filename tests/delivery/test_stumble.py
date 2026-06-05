"""Tests for stumble / hesitation burst delivery."""

from __future__ import annotations

import random

from nanobot.config.schema import MessageBurstConfig
from nanobot.delivery.burst import apply_stumble, plan_burst_delivery


def test_apply_hesitation_prepends_opener():
    cfg = MessageBurstConfig(stumble_enabled=True, stumble_probability=1.0)
    delivery = apply_stumble(["今天过得怎么样？"], "今天过得怎么样？", cfg, rng=random.Random(1))
    assert len(delivery.parts) == 2
    assert delivery.parts[1] == "今天过得怎么样？"
    assert delivery.delays_after_s[0] >= cfg.stumble_min_delay_s


def test_apply_correction_splits_sentences():
    cfg = MessageBurstConfig(
        stumble_enabled=True,
        stumble_probability=1.0,
        correction_weight=1.0,
    )
    text = "你吃饭了吗。记得早点休息。"
    delivery = apply_stumble([text], text, cfg, rng=random.Random(2))
    assert len(delivery.parts) == 2
    assert delivery.parts[0] == "你吃饭了吗。"
    assert delivery.parts[1].startswith("不对，") or delivery.parts[1].startswith("我是说——")


def test_stumble_disabled_is_noop():
    cfg = MessageBurstConfig(stumble_enabled=False, burst_probability=0.0)
    delivery = plan_burst_delivery("就一句。", cfg, rng=random.Random(0))
    assert delivery.parts == ["就一句。"]
    assert delivery.delays_after_s == []
