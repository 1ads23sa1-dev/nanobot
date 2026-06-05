"""Tests for follow-up thread persistence."""

from __future__ import annotations

from pathlib import Path

from nanobot.companion.followup import (
    FollowupThread,
    clear_followup_on_user_reply,
    read_followup_thread,
    save_followup_thread,
)
from nanobot.companion.trigger import companion_state_path


def test_save_and_read_followup_thread(tmp_path: Path):
    thread = FollowupThread(
        channel="weixin",
        chat_id="user1",
        session_key="weixin:user1",
        anchor_text="在吗？",
        origin="companion",
        anchor_sent_ms=1_700_000_000_000,
        nudge_count=0,
        max_nudges=2,
        next_check_ms=1_700_000_600_000,
        tone_hint="gentle",
    )
    save_followup_thread(tmp_path, thread)
    loaded = read_followup_thread(tmp_path)
    assert loaded is not None
    assert loaded.channel == "weixin"
    assert loaded.max_nudges == 2
    assert loaded.tone_hint == "gentle"


def test_clear_followup_on_user_reply(tmp_path: Path):
    save_followup_thread(
        tmp_path,
        FollowupThread(
            channel="weixin",
            chat_id="user1",
            session_key="weixin:user1",
            anchor_text="嗨",
            origin="reply",
            anchor_sent_ms=1,
            nudge_count=0,
            max_nudges=1,
            next_check_ms=2,
        ),
    )
    clear_followup_on_user_reply(tmp_path, channel="weixin", chat_id="user1")
    assert read_followup_thread(tmp_path) is None
    assert companion_state_path(tmp_path).exists()
