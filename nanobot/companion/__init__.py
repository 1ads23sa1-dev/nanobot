"""Proactive companion messaging (random-triggered check-ins)."""

from nanobot.companion.delivery import pick_delivery_target
from nanobot.companion.followup import (
    clear_followup,
    clear_followup_on_user_reply,
    plan_followup_after_send,
    read_followup_thread,
    run_followup_check,
)
from nanobot.companion.prompts import COMPANION_PREAMBLE, build_companion_preamble
from nanobot.companion.trigger import (
    companion_state_path,
    read_companion_state,
    record_companion_sent,
    should_send_companion_message,
)

__all__ = [
    "COMPANION_PREAMBLE",
    "build_companion_preamble",
    "clear_followup",
    "clear_followup_on_user_reply",
    "companion_state_path",
    "pick_delivery_target",
    "plan_followup_after_send",
    "read_companion_state",
    "read_followup_thread",
    "record_companion_sent",
    "run_followup_check",
    "should_send_companion_message",
]
