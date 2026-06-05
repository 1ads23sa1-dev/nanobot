"""Strip assistant-like phrasing from companion outbound text."""

from __future__ import annotations

import re

_AI_LINE_RE = re.compile(
    r"^(?:作为(?:一个)?\s*(?:AI|人工智能|语言模型|智能助手)|"
    r"I(?:'m| am) an AI|As an AI|"
    r"(?:请问)?有什么(?:可以)?帮(?:您|你)|"
    r"我可以帮(?:您|你)|"
    r"根据您的(?:要求|需求)|"
    r"以下是(?:为您)?(?:整理|提供)的).*$",
    re.I | re.M,
)
_AI_PHRASE_RE = re.compile(
    r"作为(?:一个)?\s*(?:AI|人工智能|语言模型|智能助手)[^。\n]*[。]?|"
    r"我可以帮(?:您|你)[^。\n]*[。]?|"
    r"(?:请问)?有什么(?:可以)?帮(?:您|你)[^。\n]*[。]?",
    re.I,
)
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.M)
_BULLET_BLOCK_RE = re.compile(r"(?:^[\-*•]\s+.+\n?){4,}", re.M)


def sanitize_companion_reply(text: str, *, max_chars: int = 300) -> str:
    """Remove common AI-assistant patterns and cap length."""
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned

    cleaned = _AI_LINE_RE.sub("", cleaned)
    cleaned = _AI_PHRASE_RE.sub("", cleaned)
    cleaned = _HEADING_RE.sub("", cleaned)
    cleaned = _BULLET_BLOCK_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    if max_chars > 0 and len(cleaned) > max_chars:
        cut = cleaned[:max_chars]
        for sep in ("。", "！", "？", "…", ".", "!", "?"):
            idx = cut.rfind(sep)
            if idx >= max_chars // 2:
                cleaned = cut[: idx + 1].strip()
                break
        else:
            cleaned = cut.rstrip() + "…"

    return cleaned
