"""BackgroundSummarizer — idle-time memory consolidation for layered memory."""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.memory import MemoryStore
from nanobot.agent.runner import AgentRunSpec, AgentRunner
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.providers.base import LLMProvider


# Patterns that suggest a user preference or trait
_PREFERENCE_PATTERNS = [
    (re.compile(r"(?i)I (like|hate|prefer|love|dislike|want|need|don't like).{0,50}"), "preference"),
    (re.compile(r"(?i)(always|never|usually|often|rarely).{0,50}"), "habit"),
    (re.compile(r"(?i)(remember|don't forget|make sure to).{0,50}"), "instruction"),
    (re.compile(r"(?i)(my|name is|called).{0,30}"), "identity"),
]

# Patterns for extracting structured facts
_FACT_PATTERNS = [
    re.compile(r"(\w+\s*\w+)\s*(=|is|:)\s*(.+)"),
    re.compile(r"(?i)(name|called|known as)\s*[:\-]?\s*([A-Za-z0-9_\s]+)"),
]


class BackgroundSummarizer:
    """
    Runs in the background to consolidate memory layers.

    Layered Memory Architecture:
    - RAM (Context): Managed by ContextBuilder, lives in LLM context window
    - Swap (Summary): Auto-generated conversation summaries, injected into context
    - Disk (Long-term): MEMORY.md with extracted facts and preferences
    """

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        tool_registry: ToolRegistry,
        summary_interval_turns: int = 10,
        summary_max_tokens: int = 500,
    ):
        self.provider = provider
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.tool_registry = tool_registry
        self.summary_interval = summary_interval_turns
        self.summary_max_tokens = summary_max_tokens
        self.runner = AgentRunner(provider)

        # State
        self._turn_count = 0
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the background summarizer."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("BackgroundSummarizer started")

    def stop(self) -> None:
        """Stop the background summarizer."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("BackgroundSummarizer stopped")

    def tick(self) -> None:
        """Call this after each conversation turn."""
        self._turn_count += 1
        if self._turn_count >= self.summary_interval:
            self._turn_count = 0
            # Trigger async consolidation without blocking
            asyncio.create_task(self._consolidate())

    async def _run(self) -> None:
        """Main background loop."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                if self._should_consolidate():
                    await self._consolidate()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("BackgroundSummarizer error")

    def _should_consolidate(self) -> bool:
        """Check if consolidation is needed."""
        # Check last summary timestamp
        summary_file = self.workspace / "memory" / "_last_summary.txt"
        if not summary_file.exists():
            return True

        try:
            last_time = datetime.fromtimestamp(summary_file.stat().st_mtime)
            return (datetime.now() - last_time) > timedelta(hours=1)
        except Exception:
            return True

    async def _consolidate(self) -> None:
        """
        Core consolidation: extract facts, update MEMORY.md.
        This runs in background and doesn't block the main agent.
        """
        logger.info("Starting memory consolidation")

        # Read recent history
        entries = self.memory.read_unprocessed_history(
            since_cursor=self.memory.get_last_dream_cursor()
        )

        if len(entries) < 3:
            logger.debug("Not enough new entries to consolidate")
            return

        # Generate summary
        summary = await self._generate_summary(entries[-10:])  # Last 10 entries

        if summary:
            # Update long-term memory with extracted facts
            self._update_long_term_memory(summary)

            # Update dream cursor
            if entries:
                self.memory.set_last_dream_cursor(entries[-1].get("cursor", 0))

            # Touch summary timestamp
            (self.workspace / "memory" / "_last_summary.txt").touch()

        logger.info("Memory consolidation complete")

    async def _generate_summary(self, entries: list[dict[str, Any]]) -> str:
        """Generate a summary of recent entries using LLM."""
        history_text = "\n".join(
            f"[{e.get('timestamp', '?')}] {e.get('content', '')}"
            for e in entries
        )

        prompt = f"""Analyze these conversation entries and extract:
1. Key facts about the user (preferences, habits, goals, identity)
2. Important decisions or conclusions made
3. Any instructions or reminders

Be concise. Only extract things worth remembering long-term.

Recent entries:
{history_text}

Output in this format:
FACTS:
- (fact 1)
- (fact 2)
CONCLUSIONS:
- (conclusion 1)
REMINDERS:
- (reminder 1)
"""

        spec = AgentRunSpec(
            initial_messages=[{"role": "user", "content": prompt}],
            tools=self.tool_registry,
            model=self.provider.get_default_model(),
            max_iterations=1,
            max_tool_result_chars=self.summary_max_tokens,
            temperature=0.3,
        )

        try:
            result = await self.runner.run(spec)
            return result.final_content or ""
        except Exception:
            logger.exception("Summary generation failed")
            return ""

    def _update_long_term_memory(self, summary: str) -> None:
        """Update MEMORY.md with new summary content."""
        current = self.memory.read_memory()

        # Parse summary into sections
        facts = self._extract_section(summary, "FACTS")
        conclusions = self._extract_section(summary, "CONCLUSIONS")
        reminders = self._extract_section(summary, "REMINDERS")

        # Build update
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entries = [f"\n## Summary ({timestamp})"]

        if facts:
            new_entries.append("### Facts")
            new_entries.append(facts)

        if conclusions:
            new_entries.append("### Conclusions")
            new_entries.append(conclusions)

        if reminders:
            new_entries.append("### Reminders")
            new_entries.append(reminders)

        new_content = "\n".join(new_entries)

        # Append to memory
        if current:
            updated = current + "\n" + new_content
        else:
            updated = f"# Memory\n\nLast updated: {timestamp}\n\n{new_content}"

        self.memory.write_memory(updated)

    def _extract_section(self, text: str, header: str) -> str:
        """Extract a section from summary text."""
        pattern = rf"{header}[:\s]*(.*?)(?=\n[A-Z]|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def extract_preferences(self, text: str) -> list[dict[str, str]]:
        """
        Extract user preferences from any text.
        Returns list of {pattern, preference, confidence}.
        """
        preferences = []

        for pattern, ptype in _PREFERENCE_PATTERNS:
            for match in pattern.finditer(text):
                preferences.append({
                    "type": ptype,
                    "text": match.group(0),
                    "preference": self._normalize_preference(match.group(0)),
                    "confidence": "high" if match.group(0).startswith("I ") else "medium",
                })

        return preferences

    def _normalize_preference(self, text: str) -> str:
        """Normalize preference text for storage."""
        # Remove leading "I " or "I '" etc
        normalized = re.sub(r"^I\s+(like|hate|love|dislike|prefer|need|want|don't like)\s+", "", text, flags=re.IGNORECASE)
        # Capitalize first letter
        return normalized.strip()[0].upper() + normalized.strip()[1:] if normalized.strip() else text
