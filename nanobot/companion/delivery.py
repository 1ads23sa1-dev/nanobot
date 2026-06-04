"""Resolve where proactive companion messages should be delivered."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nanobot.session.manager import SessionManager


def pick_delivery_target(
    *,
    pinned_channel: str,
    pinned_chat_id: str,
    enabled_channels: set[str],
    session_manager: SessionManager,
) -> tuple[str, str]:
    """Return (channel, chat_id) for proactive delivery.

    Uses pinned channel/chat_id when configured; otherwise falls back to the first
    routable non-cli session among enabled channels.
    """
    channel = (pinned_channel or "").strip()
    chat_id = (pinned_chat_id or "").strip()
    if channel and chat_id and channel in enabled_channels:
        return channel, chat_id

    for item in session_manager.list_sessions():
        key = item.get("key") or ""
        if ":" not in key:
            continue
        session_channel, session_chat_id = key.split(":", 1)
        if session_channel in {"cli", "system", "api"}:
            continue
        if session_channel in enabled_channels and session_chat_id:
            return session_channel, session_chat_id
    return "cli", "direct"
