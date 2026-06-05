"""Prompt fragments for proactive companion turns."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from nanobot.utils.helpers import load_bundled_template, truncate_text

if TYPE_CHECKING:
    from nanobot.session.manager import SessionManager

_COMPANION_PREAMBLE_CORE = (
    "[Proactive companion message — you are 丰川祥子 (小祥). "
    "Your reply goes directly to the user's WeChat. "
    "Write in 简体中文 in her voice: proud but warm, short WeChat-style, "
    "1–3 sentences per bubble. You may send 1–2 bubbles separated by a line "
    "containing only `---` when a second short thought feels natural "
    "(most of the time use a single bubble). "
    "You may reference shared memory. "
    "Do NOT mention cron, heartbeat, random triggers, internal files, or being an AI assistant. "
    "Do NOT use butler/report language. Output ONLY the message text.]"
)

# Backward-compatible constant (tests / imports).
COMPANION_PREAMBLE = (
    f"{_COMPANION_PREAMBLE_CORE}\n\n"
    "Send a spontaneous check-in right now — like 小祥 texting because she just thought of the user."
)


def _read_workspace_excerpt(path: Path, *, max_chars: int = 1200) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not text:
        return ""
    bundled = load_bundled_template(path.name)
    if bundled and text.strip() == bundled.strip():
        return ""
    return truncate_text(text, max_chars)


def _memory_user_lines(workspace: Path, *, max_lines: int = 5) -> list[str]:
    memory_file = workspace / "memory" / "MEMORY.md"
    try:
        raw = memory_file.read_text(encoding="utf-8")
    except OSError:
        return []
    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            lines.append(stripped[2:].strip())
        if len(lines) >= max_lines:
            break
    return lines


def _hours_since_last_chat(
    session_manager: SessionManager | None,
    channel: str,
    chat_id: str,
) -> float | None:
    if not session_manager or not channel or not chat_id:
        return None
    session_key = f"{channel}:{chat_id}"
    detail = session_manager.read_session_file(session_key)
    if not detail:
        return None
    updated_at = detail.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        return None
    try:
        last = datetime.fromisoformat(updated_at)
    except ValueError:
        return None
    elapsed_h = (datetime.now() - last).total_seconds() / 3600
    return max(0.0, elapsed_h)


def build_companion_preamble(
    workspace: Path,
    *,
    channel: str = "",
    chat_id: str = "",
    session_manager: SessionManager | None = None,
) -> str:
    """Build a context-rich proactive companion prompt."""
    parts = [_COMPANION_PREAMBLE_CORE]

    user_excerpt = _read_workspace_excerpt(workspace / "USER.md")
    if user_excerpt:
        parts.append(f"\n[User profile excerpt]\n{user_excerpt}")

    memory_lines = _memory_user_lines(workspace)
    if memory_lines:
        bullets = "\n".join(f"- {line}" for line in memory_lines)
        parts.append(f"\n[Shared memory highlights]\n{bullets}")

    hours = _hours_since_last_chat(session_manager, channel, chat_id)
    if hours is not None:
        if hours < 1:
            parts.append("\n[Timing] You chatted with the user within the last hour — keep the check-in light, no repeated greetings.")
        elif hours < 24:
            parts.append(f"\n[Timing] About {hours:.1f} hours since the last conversation.")
        else:
            parts.append(f"\n[Timing] About {hours:.0f} hours since the last conversation — you may gently reference missing them.")

    parts.append(
        "\nSend a spontaneous check-in right now — like 小祥 texting because she just thought of the user."
    )
    return "\n".join(parts)
