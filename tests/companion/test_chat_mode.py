"""Tests for lightweight chat detection."""

from nanobot.companion.chat_mode import is_lightweight_chat


def test_casual_greeting_is_lightweight():
    assert is_lightweight_chat("在吗")
    assert is_lightweight_chat("今天好累啊")


def test_task_message_is_not_lightweight():
    assert not is_lightweight_chat("帮我查一下天气")
    assert not is_lightweight_chat("run pytest tests/")


def test_command_and_media_skip_lightweight():
    assert not is_lightweight_chat("/dream", is_command=True)
    assert not is_lightweight_chat("看看这个", has_media=True)
