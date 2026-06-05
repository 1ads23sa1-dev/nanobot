"""Tests for companion proactive preamble."""

from pathlib import Path

from nanobot.companion.prompts import build_companion_preamble


def test_build_companion_preamble_includes_core(tmp_path: Path):
    (tmp_path / "USER.md").write_text("# User\n\n- **Name**: 测试用户\n", encoding="utf-8")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "MEMORY.md").write_text(
        "# Memory\n\n- 用户最近在准备考试\n",
        encoding="utf-8",
    )
    prompt = build_companion_preamble(tmp_path, channel="weixin", chat_id="u1")
    assert "丰川祥子" in prompt
    assert "测试用户" in prompt or "User profile" in prompt
    assert "spontaneous check-in" in prompt.lower() or "Send a spontaneous" in prompt
