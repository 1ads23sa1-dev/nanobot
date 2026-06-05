"""AI-driven follow-up nudges when the user stays silent after a bot message."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from zoneinfo import ZoneInfo

from loguru import logger

from nanobot.companion.trigger import companion_state_path, in_quiet_hours, read_companion_state
from nanobot.utils.prompt_templates import render_template

if TYPE_CHECKING:
    from nanobot.config.schema import CompanionConfig
    from nanobot.providers.base import LLMProvider
    from nanobot.session.manager import SessionManager

FollowupOrigin = Literal["companion", "reply", "proactive"]

_PLAN_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "plan_followup",
            "description": "Plan whether and how to follow up if the user stays silent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "should_followup": {
                        "type": "boolean",
                        "description": "true if follow-up nudges may be appropriate when user is silent",
                    },
                    "max_nudges": {
                        "type": "integer",
                        "description": "Max additional nudge messages (0-3)",
                        "minimum": 0,
                        "maximum": 3,
                    },
                    "first_wait_minutes": {
                        "type": "integer",
                        "description": "Minutes to wait before first follow-up check",
                        "minimum": 5,
                        "maximum": 90,
                    },
                    "tone_hint": {
                        "type": "string",
                        "description": "Brief tone guidance for nudges",
                    },
                    "reason": {
                        "type": "string",
                        "description": "One-sentence rationale",
                    },
                },
                "required": ["should_followup", "max_nudges", "first_wait_minutes"],
            },
        },
    }
]

_NUDGE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "decide_followup_nudge",
            "description": "Decide whether to nudge, reschedule, or abandon follow-up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["send", "reschedule", "skip", "abandon"],
                    },
                    "wait_minutes": {
                        "type": "integer",
                        "description": "Minutes until next check (reschedule/skip)",
                        "minimum": 5,
                        "maximum": 60,
                    },
                    "nudge_text": {
                        "type": "string",
                        "description": "Message to send when action=send",
                    },
                    "reason": {
                        "type": "string",
                    },
                },
                "required": ["action"],
            },
        },
    }
]


@dataclass(frozen=True)
class FollowupThread:
    """Pending follow-up state for one chat."""

    channel: str
    chat_id: str
    session_key: str
    anchor_text: str
    origin: FollowupOrigin
    anchor_sent_ms: int
    nudge_count: int
    max_nudges: int
    next_check_ms: int
    tone_hint: str = ""


@dataclass(frozen=True)
class FollowupPlanResult:
    scheduled: bool
    reason: str = ""


@dataclass(frozen=True)
class FollowupCheckResult:
    action: Literal["none", "sent", "rescheduled", "abandoned", "skipped"]
    reason: str = ""


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_state(path: Path) -> dict[str, Any]:
    return read_companion_state(path)


def clear_followup(workspace: Path) -> None:
    path = companion_state_path(workspace)
    state = _load_state(path)
    if "followup" not in state:
        return
    state.pop("followup", None)
    _write_state(path, state)
    logger.debug("Cleared follow-up thread")


def clear_followup_on_user_reply(workspace: Path, *, channel: str, chat_id: str) -> None:
    path = companion_state_path(workspace)
    state = _load_state(path)
    followup = state.get("followup")
    if not isinstance(followup, dict):
        return
    if followup.get("channel") == channel and str(followup.get("chat_id")) == str(chat_id):
        state.pop("followup", None)
        _write_state(path, state)
        logger.info("Follow-up cleared after user reply on {}:{}", channel, chat_id)


def read_followup_thread(workspace: Path) -> FollowupThread | None:
    state = _load_state(companion_state_path(workspace))
    raw = state.get("followup")
    if not isinstance(raw, dict):
        return None
    try:
        return FollowupThread(
            channel=str(raw["channel"]),
            chat_id=str(raw["chat_id"]),
            session_key=str(raw.get("session_key") or f"{raw['channel']}:{raw['chat_id']}"),
            anchor_text=str(raw.get("anchor_text") or ""),
            origin=raw.get("origin") or "reply",
            anchor_sent_ms=int(raw["anchor_sent_ms"]),
            nudge_count=int(raw.get("nudge_count") or 0),
            max_nudges=int(raw.get("max_nudges") or 0),
            next_check_ms=int(raw["next_check_ms"]),
            tone_hint=str(raw.get("tone_hint") or ""),
        )
    except (KeyError, TypeError, ValueError):
        return None


def save_followup_thread(workspace: Path, thread: FollowupThread) -> None:
    path = companion_state_path(workspace)
    state = _load_state(path)
    state["followup"] = {
        "channel": thread.channel,
        "chat_id": thread.chat_id,
        "session_key": thread.session_key,
        "anchor_text": thread.anchor_text,
        "origin": thread.origin,
        "anchor_sent_ms": thread.anchor_sent_ms,
        "nudge_count": thread.nudge_count,
        "max_nudges": thread.max_nudges,
        "next_check_ms": thread.next_check_ms,
        "tone_hint": thread.tone_hint,
    }
    _write_state(path, state)


def _parse_timestamp(iso: str) -> float | None:
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return None


def _format_history(session_manager: SessionManager, session_key: str, *, limit: int = 12) -> str:
    session = session_manager.get_or_create(session_key)
    lines: list[str] = []
    for msg in session.messages[-limit:]:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, list):
            parts = [
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            content = " ".join(parts)
        text = str(content).strip()
        if not text:
            continue
        if len(text) > 300:
            text = text[:297] + "..."
        lines.append(f"{role}: {text}")
    return "\n".join(lines) if lines else "(no prior messages)"


def _local_time_str(timezone: str, now_ms: int) -> str:
    try:
        dt = datetime.fromtimestamp(now_ms / 1000, tz=ZoneInfo(timezone))
    except Exception:
        dt = datetime.fromtimestamp(now_ms / 1000).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M %Z")


def user_replied_since_anchor(
    session_manager: SessionManager,
    thread: FollowupThread,
) -> bool:
    session = session_manager.get_or_create(thread.session_key)
    anchor_s = thread.anchor_sent_ms / 1000
    for msg in reversed(session.messages):
        if msg.get("role") != "user":
            continue
        ts = _parse_timestamp(str(msg.get("timestamp") or ""))
        if ts is None:
            return True
        if ts >= anchor_s - 2:
            return True
    return False


async def plan_followup_after_send(
    *,
    workspace: Path,
    cfg: CompanionConfig,
    provider: LLMProvider,
    model: str,
    session_manager: SessionManager,
    channel: str,
    chat_id: str,
    session_key: str,
    anchor_text: str,
    origin: FollowupOrigin,
    timezone: str,
) -> FollowupPlanResult:
    """Phase 1: AI decides whether to track this thread for follow-up nudges."""
    if not cfg.followup_enabled or not anchor_text.strip():
        return FollowupPlanResult(False, "followup disabled or empty anchor")

    now_ms = int(time.time() * 1000)
    history_text = _format_history(session_manager, session_key)
    try:
        response = await provider.chat_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": render_template("agent/followup_plan.md", part="system"),
                },
                {
                    "role": "user",
                    "content": render_template(
                        "agent/followup_plan.md",
                        part="user",
                        origin=origin,
                        local_time=_local_time_str(timezone, now_ms),
                        anchor_text=anchor_text.strip(),
                        history_text=history_text,
                    ),
                },
            ],
            tools=_PLAN_TOOL,
            model=model,
            max_tokens=256,
            temperature=0.4,
        )
    except Exception:
        logger.exception("plan_followup_after_send failed")
        return FollowupPlanResult(False, "planner error")

    if not response.should_execute_tools or not response.tool_calls:
        return FollowupPlanResult(False, "no tool call")

    args = response.tool_calls[0].arguments
    if not args.get("should_followup"):
        return FollowupPlanResult(False, args.get("reason") or "planner declined")

    max_nudges = min(
        int(args.get("max_nudges") or 0),
        cfg.max_followup_nudges,
    )
    if max_nudges <= 0:
        return FollowupPlanResult(False, "max_nudges=0")

    wait_minutes = int(args.get("first_wait_minutes") or 20)
    wait_minutes = max(5, min(wait_minutes, 90))
    next_check_ms = now_ms + wait_minutes * 60 * 1000

    thread = FollowupThread(
        channel=channel,
        chat_id=chat_id,
        session_key=session_key,
        anchor_text=anchor_text.strip(),
        origin=origin,
        anchor_sent_ms=now_ms,
        nudge_count=0,
        max_nudges=max_nudges,
        next_check_ms=next_check_ms,
        tone_hint=str(args.get("tone_hint") or ""),
    )
    save_followup_thread(workspace, thread)
    logger.info(
        "Follow-up planned for {}:{} max_nudges={} first_check_in={}m ({})",
        channel,
        chat_id,
        max_nudges,
        wait_minutes,
        args.get("reason", ""),
    )
    return FollowupPlanResult(True, str(args.get("reason") or "scheduled"))


async def run_followup_check(
    *,
    workspace: Path,
    cfg: CompanionConfig,
    provider: LLMProvider,
    model: str,
    session_manager: SessionManager,
    timezone: str,
    deliver,
) -> FollowupCheckResult:
    """Phase 2: cron tick — AI decides send / reschedule / abandon."""
    if not cfg.followup_enabled:
        return FollowupCheckResult("none", "disabled")

    thread = read_followup_thread(workspace)
    if thread is None:
        return FollowupCheckResult("none", "no pending thread")

    now_ms = int(time.time() * 1000)
    if now_ms < thread.next_check_ms:
        return FollowupCheckResult("none", "not yet due")

    try:
        now_local = datetime.fromtimestamp(now_ms / 1000, tz=ZoneInfo(timezone))
    except Exception:
        now_local = datetime.fromtimestamp(now_ms / 1000).astimezone()

    if in_quiet_hours(
        now=now_local,
        quiet_start=cfg.quiet_hours_start,
        quiet_end=cfg.quiet_hours_end,
    ):
        save_followup_thread(
            workspace,
            replace(thread, next_check_ms=now_ms + 30 * 60 * 1000),
        )
        return FollowupCheckResult("rescheduled", "quiet hours")

    if user_replied_since_anchor(session_manager, thread):
        clear_followup(workspace)
        return FollowupCheckResult("abandoned", "user replied")

    if thread.nudge_count >= thread.max_nudges:
        clear_followup(workspace)
        return FollowupCheckResult("abandoned", "max nudges reached")

    minutes_since = max(0, int((now_ms - thread.anchor_sent_ms) / 60_000))
    history_text = _format_history(session_manager, thread.session_key)

    try:
        response = await provider.chat_with_retry(
            messages=[
                {
                    "role": "system",
                    "content": render_template("agent/followup_nudge.md", part="system"),
                },
                {
                    "role": "user",
                    "content": render_template(
                        "agent/followup_nudge.md",
                        part="user",
                        origin=thread.origin,
                        local_time=_local_time_str(timezone, now_ms),
                        anchor_text=thread.anchor_text,
                        tone_hint=thread.tone_hint or "(none)",
                        nudge_count=thread.nudge_count,
                        max_nudges=thread.max_nudges,
                        minutes_since_anchor=minutes_since,
                        history_text=history_text,
                    ),
                },
            ],
            tools=_NUDGE_TOOL,
            model=model,
            max_tokens=320,
            temperature=0.5,
        )
    except Exception:
        logger.exception("run_followup_check failed")
        return FollowupCheckResult("skipped", "evaluator error")

    if not response.should_execute_tools or not response.tool_calls:
        return FollowupCheckResult("skipped", "no tool call")

    args = response.tool_calls[0].arguments
    action = str(args.get("action") or "skip")
    reason = str(args.get("reason") or "")

    if action == "abandon":
        clear_followup(workspace)
        return FollowupCheckResult("abandoned", reason)

    wait_minutes = int(args.get("wait_minutes") or 15)
    wait_minutes = max(5, min(wait_minutes, 60))

    if action == "send":
        nudge_text = str(args.get("nudge_text") or "").strip()
        if not nudge_text:
            save_followup_thread(
                workspace,
                replace(thread, next_check_ms=now_ms + wait_minutes * 60 * 1000),
            )
            return FollowupCheckResult("skipped", "empty nudge_text")

        from nanobot.bus.events import OutboundMessage

        await deliver(
            OutboundMessage(
                channel=thread.channel,
                chat_id=thread.chat_id,
                content=nudge_text,
                metadata={"_followup_nudge": True},
            ),
            record=True,
            session_key=thread.session_key,
        )

        new_count = thread.nudge_count + 1
        if new_count >= thread.max_nudges:
            clear_followup(workspace)
            return FollowupCheckResult("sent", f"final nudge: {reason}")

        min_gap_ms = cfg.min_followup_interval_s * 1000
        save_followup_thread(
            workspace,
            replace(
                thread,
                nudge_count=new_count,
                next_check_ms=now_ms + max(min_gap_ms, wait_minutes * 60 * 1000),
            ),
        )
        return FollowupCheckResult("sent", reason)

    save_followup_thread(
        workspace,
        replace(thread, next_check_ms=now_ms + wait_minutes * 60 * 1000),
    )
    if action == "reschedule":
        return FollowupCheckResult("rescheduled", reason)
    return FollowupCheckResult("skipped", reason)
