"""PhilosopherAgent — slow-think agent with layered memory and self-verification."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.memory import MemoryStore
from nanobot.agent.runner import AgentRunSpec, AgentRunResult, AgentRunner
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.providers.base import LLMProvider


@dataclass
class ReflectionResult:
    """Result of the reflection/self-correction phase."""
    intent_analysis: str       # What the user really wants
    context_links: list[str]   # Related memories/context
    logic_gaps: list[str]      # Potential issues to address
    self_correction: str       # How we corrected ourselves
    plan: list[str]           # Actionable steps


class PhilosopherAgent:
    """
    A thoughtful agent that thinks before acting.

    Architecture:
    1. THINK — Analyze intent, retrieve context, identify gaps
    2. PLAN  — Create action steps with verification points
    3. EXECUTE — Run tools with sandbox verification
    4. REFINE — Self-correct based on results, then respond
    """

    THINK_PROMPT = """<think>
You are nanobot's internal reasoning module. Before responding to the user:

1. INTENT: What does the user really want? (not just the words)
2. CONTEXT: What relevant memories or past context apply here?
3. GAPS: What logical gaps, assumptions, or risks exist?
4. CORRECTION: If you catch yourself about to make a flawed response, correct it now.

Be direct and honest. Think silently, then output your refined response.
</think>

User: {user_message}

Relevant Memory:
{memory_context}

Recent History (last 5 entries):
{history}

Think silently first, then respond as nanobot."""

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        tool_registry: ToolRegistry,
        max_verification_attempts: int = 2,
    ):
        self.provider = provider
        self.workspace = workspace
        self.tool_registry = tool_registry
        self.max_verification_attempts = max_verification_attempts
        self.memory = MemoryStore(workspace)
        self.runner = AgentRunner(provider)

    async def think(self, user_message: str) -> ReflectionResult:
        """
        Phase 1: Slow thinking - analyze before responding.
        """
        memory_context = self.memory.read_memory() or "No long-term memory yet."
        history_entries = self.memory.read_unprocessed_history(
            since_cursor=self.memory.get_last_dream_cursor()
        )[-5:]
        history_text = "\n".join(
            f"- [{e.get('timestamp', '?')}] {e.get('content', '')}"
            for e in history_entries
        ) or "No recent history."

        prompt = self.THINK_PROMPT.format(
            user_message=user_message,
            memory_context=memory_context,
            history=history_text,
        )

        # Call LLM for reflection
        spec = AgentRunSpec(
            initial_messages=[{"role": "user", "content": prompt}],
            tools=self.tool_registry,
            model=self.provider.get_default_model(),
            max_iterations=1,
            max_tool_result_chars=2000,
            temperature=0.3,  # Lower temp for analytical thinking
        )

        result = await self.runner.run(spec)
        reflection_text = result.final_content or ""

        # Parse reflection into structured result
        return self._parse_reflection(reflection_text, user_message)

    def _parse_reflection(self, text: str, original_message: str) -> ReflectionResult:
        """Parse the reflection output into structured components."""
        return ReflectionResult(
            intent_analysis=self._extract_section(text, "INTENT", default=original_message),
            context_links=self._extract_list(text, "CONTEXT"),
            logic_gaps=self._extract_list(text, "GAPS"),
            self_correction=self._extract_section(text, "CORRECTION", default=""),
            plan=self._extract_list(text, "PLAN"),
        )

    def _extract_section(self, text: str, header: str, default: str = "") -> str:
        """Extract a section of text after a header."""
        import re
        pattern = rf"{header}[:\s]*(.*?)(?=\n[A-Z]|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else default

    def _extract_list(self, text: str, header: str) -> list[str]:
        """Extract a list under a header."""
        import re
        pattern = rf"{header}[:\s]*(.*?)(?=\n[A-Z]|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if not match:
            return []
        items = re.findall(r"[-*]\s*(.+?)(?=\n[-*]|$)", match.group(1), re.DOTALL)
        return [item.strip() for item in items if item.strip()]

    async def execute_with_verification(
        self,
        spec: AgentRunSpec,
    ) -> AgentRunResult:
        """
        Phase 2: Execute with self-verification闭环.
        If tools were called, run them in sandbox and check for errors.
        """
        result = await self.runner.run(spec)

        # Self-verification loop
        for attempt in range(self.max_verification_attempts):
            if not result.tool_events:
                # No tools used, no verification needed
                break

            has_errors = any(
                evt.get("status") == "error" for evt in result.tool_events
            )

            if not has_errors:
                break

            logger.info(
                "PhilosopherAgent self-correction round {}/{}",
                attempt + 1, self.max_verification_attempts,
            )

            # Inject error feedback and retry
            error_summary = self._summarize_errors(result.tool_events)
            correction_prompt = (
                f"The previous attempt had errors:\n{error_summary}\n\n"
                f"Please correct and retry only the failed parts."
            )

            # Continue with corrected context
            spec.initial_messages.append({
                "role": "user",
                "content": correction_prompt,
            })
            result = await self.runner.run(spec)

        return result

    def _summarize_errors(self, tool_events: list[dict]) -> str:
        """Summarize tool errors for correction prompt."""
        errors = [
            f"- {evt.get('name', '?')}: {evt.get('error', 'unknown error')}"
            for evt in tool_events
            if evt.get("status") == "error"
        ]
        return "\n".join(errors) if errors else "No errors found."

    async def run(
        self,
        user_message: str,
        context_messages: list[dict[str, Any]],
    ) -> AgentRunResult:
        """
        Main entry point: Think → Execute with verification → Refine.
        """
        # Phase 1: Think
        reflection = await self.think(user_message)

        # Build context with reflection insights
        refined_prompt = self._build_refined_prompt(user_message, reflection)

        # Phase 2: Execute with verification
        spec = AgentRunSpec(
            initial_messages=context_messages + [{"role": "user", "content": refined_prompt}],
            tools=self.tool_registry,
            model=self.provider.get_default_model(),
            max_iterations=5,
            max_tool_result_chars=8000,
            temperature=0.7,
        )

        result = await self.execute_with_verification(spec)

        # Phase 3: Refine final response (add reflection summary if significant)
        if reflection.logic_gaps or reflection.self_correction:
            refinement_note = self._build_refinement_note(reflection)
            if result.final_content and refinement_note:
                result.final_content = result.final_content.rstrip() + "\n\n" + refinement_note

        return result

    def _build_refined_prompt(self, user_message: str, reflection: ReflectionResult) -> str:
        """Build prompt enriched with reflection insights."""
        parts = [f"User: {user_message}"]

        if reflection.context_links:
            parts.append(f"\nRelevant context: {', '.join(reflection.context_links)}")

        if reflection.plan:
            parts.append(f"\nAction plan: {' → '.join(reflection.plan)}")

        if reflection.self_correction:
            parts.append(f"\nSelf-correction applied: {reflection.self_correction}")

        return "\n".join(parts)

    def _build_refinement_note(self, reflection: ReflectionResult) -> str:
        """Build a note about the reflection process (optional, for transparency)."""
        if not reflection.logic_gaps and not reflection.self_correction:
            return ""

        notes = []
        if reflection.logic_gaps:
            notes.append(f"Considered: {', '.join(reflection.logic_gaps[:2])}")
        if reflection.self_correction:
            notes.append(f"Corrected: {reflection.self_correction[:100]}")

        return f"[Reflection: {'; '.join(notes)}]"
