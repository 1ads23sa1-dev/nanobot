"""Proactive companion messaging (random-triggered check-ins)."""

from nanobot.companion.delivery import pick_delivery_target
from nanobot.companion.prompts import COMPANION_PREAMBLE
from nanobot.companion.trigger import (
    companion_state_path,
    read_companion_state,
    record_companion_sent,
    should_send_companion_message,
)

__all__ = [
    "COMPANION_PREAMBLE",
    "companion_state_path",
    "pick_delivery_target",
    "read_companion_state",
    "record_companion_sent",
    "should_send_companion_message",
]
