"""Tests for companion reply sanitization."""

from nanobot.companion.sanitize import sanitize_companion_reply


def test_strips_ai_assistant_phrases():
    text = "作为 AI 助手，我可以帮你。\n今天怎么样？"
    cleaned = sanitize_companion_reply(text)
    assert "作为 AI" not in cleaned
    assert "今天怎么样" in cleaned


def test_truncates_long_reply():
    long_text = "好。" * 200
    cleaned = sanitize_companion_reply(long_text, max_chars=50)
    assert len(cleaned) <= 51
