"""Heuristics for lightweight companion chat (no tools, short replies)."""

from __future__ import annotations

import re

_TASK_HINTS = re.compile(
    r"(帮我|帮忙|请|查一下|搜索|运行|执行|写个|写一个|创建|修改|删除|读取|打开|下载|"
    r"run|exec|grep|read_file|write_file|apply_patch|web_search|cron|/dream|/new)",
    re.I,
)
_URL_RE = re.compile(r"https?://|www\.", re.I)
_PATH_RE = re.compile(r"(?:^|[\s'\"`])(?:/|~|\.{1,2}/)[^\s'\"`]+")
_MAX_CASUAL_CHARS = 280


def is_lightweight_chat(
    content: str,
    *,
    has_media: bool = False,
    is_command: bool = False,
) -> bool:
    """Return True when the inbound message looks like casual chit-chat."""
    if is_command or has_media:
        return False

    text = (content or "").strip()
    if not text:
        return False
    if text.startswith("/"):
        return False
    if len(text) > _MAX_CASUAL_CHARS:
        return False
    if _URL_RE.search(text) or _PATH_RE.search(text):
        return False
    if _TASK_HINTS.search(text):
        return False
    return True
