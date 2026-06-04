"""Memory search tool — searches nanobot memory and local documents."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.agent.memory import MemoryStore
from nanobot.agent.rag.bm25 import BM25Index
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.context import ToolContext


class MemorySearchTool(Tool):
    _plugin_discoverable = False
    """
    Search nanobot's memory and local documents.

    Provides two search modes:
    - memory: Search MEMORY.md and history.jsonl
    - docs: Search workspace documents using BM25
    - all: Search both (default)
    """

    name = "memory_search"
    description = """Search nanobot's memory and local documents.

Use this when you need to find information that the user mentioned before,
or when answering questions about content in the workspace.

Examples:
- User asks "what did I say about X?" → search memory
- User asks "do I have any notes about Y?" → search docs
- User asks "remember when I mentioned Z?" → search all
"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                    "minLength": 1,
                },
                "scope": {
                    "type": "string",
                    "enum": ["memory", "docs", "all"],
                    "description": "Search scope: 'memory' (MEMORY.md + history), 'docs' (workspace files), 'all' (default)",
                    "default": "all",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return per scope (default: 5)",
                },
            },
            "required": ["query"],
        }

    @property
    def read_only(self) -> bool:
        return True

    def __init__(
        self,
        workspace: Path,
        memory_store: MemoryStore | None = None,
        max_results: int = 5,
    ):
        super().__init__()
        self.workspace = workspace
        self.memory_store = memory_store or MemoryStore(workspace)
        self.max_results = max_results
        self._bm25: BM25Index | None = None
        self._bm25_built = False

    def _get_bm25(self) -> BM25Index:
        """Get or create BM25 index."""
        if self._bm25 is None:
            self._bm25 = BM25Index(self.workspace)
        return self._bm25

    def _ensure_bm25_built(self) -> None:
        """Build BM25 index if not already built."""
        if not self._bm25_built:
            bm25 = self._get_bm25()
            count = bm25.index_documents()
            logger.debug("BM25 indexed {} documents", count)
            self._bm25_built = True

    async def execute(
        self,
        query: str,
        scope: str = "all",
        k: int | None = None,
    ) -> str:
        """
        Search memory and/or documents.

        Args:
            query: Search query string
            scope: "memory" | "docs" | "all" (default: "all")
            k: Number of results per scope (default: max_results)

        Returns:
            Formatted search results
        """
        if not query or not query.strip():
            return "Error: Empty query"

        k = k or self.max_results
        results: list[str] = []

        if scope in ("memory", "all"):
            memory_results = self._search_memory(query, k)
            if memory_results:
                results.append("## Memory Search Results\n")
                results.append(memory_results)
            else:
                results.append("## Memory Search: No results found")

        if scope in ("docs", "all"):
            # Ensure BM25 index is built (async-safe)
            if asyncio.get_event_loop().is_running():
                # We're in async context, run in executor
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._ensure_bm25_built)
            else:
                self._ensure_bm25_built()

            docs_results = self._search_docs(query, k)
            if docs_results:
                results.append("\n## Document Search Results\n")
                results.append(docs_results)
            elif scope == "docs":
                results.append("## Document Search: No results found")

        if not results:
            return "No results found for the query."

        return "\n".join(results)

    def _search_memory(self, query: str, k: int) -> str:
        """Search memory files (MEMORY.md and history.jsonl)."""
        memory_content = self.memory_store.read_memory()
        history_entries = self.memory_store._read_entries()

        matches: list[tuple[str, float, str]] = []

        # Search MEMORY.md
        if memory_content:
            query_lower = query.lower()
            # Simple keyword matching for memory
            content_lines = memory_content.split("\n")
            for i, line in enumerate(content_lines):
                if query_lower in line.lower():
                    # Get surrounding context (3 lines before and after)
                    start = max(0, i - 3)
                    end = min(len(content_lines), i + 4)
                    snippet = "\n".join(content_lines[start:end])
                    score = line.lower().count(query_lower) * 1.0
                    matches.append((f"MEMORY.md (line {i+1})", score, snippet))

        # Search history.jsonl
        for entry in history_entries:
            content = entry.get("content", "")
            if content and query.lower() in content.lower():
                timestamp = entry.get("timestamp", "?")
                score = content.lower().count(query.lower()) * 0.5
                # Get first 200 chars as snippet
                snippet = content[:200] + "..." if len(content) > 200 else content
                matches.append((f"history @ {timestamp}", score, snippet))

        # Sort by score and return top k
        matches.sort(key=lambda x: x[1], reverse=True)
        matches = matches[:k]

        if not matches:
            return ""

        lines = []
        for path, score, snippet in matches:
            lines.append(f"**{path}** (relevance: {score:.1f})")
            lines.append("```")
            lines.append(snippet[:300])
            lines.append("```\n")

        return "\n".join(lines)

    def _search_docs(self, query: str, k: int) -> str:
        """Search workspace documents using BM25."""
        bm25 = self._get_bm25()
        self._ensure_bm25_built()

        results = bm25.search(query, k=k)
        if not results:
            return ""

        lines = []
        for path, score, snippet in results:
            lines.append(f"**{path}** (score: {score:.2f})")
            lines.append("```")
            lines.append(snippet[:200])
            lines.append("```\n")

        return "\n".join(lines)

    def invalidate_index(self) -> None:
        """Invalidate BM25 index, forcing rebuild on next search."""
        self._bm25_built = False
        self._bm25 = None
        logger.debug("BM25 index invalidated")


class MemorySearchToolWrapper(Tool):
    """
    Async wrapper for MemorySearchTool that runs in executor.
    This allows the sync tool to work in async context.
    """

    @classmethod
    def create(cls, ctx: ToolContext) -> Tool:
        return cls(
            workspace=Path(ctx.workspace),
            memory_store=ctx.memory_store,
        )

    name = "memory_search"
    description = MemorySearchTool.description

    @property
    def parameters(self) -> dict[str, Any]:
        return MemorySearchTool.parameters.fget(None) if hasattr(MemorySearchTool, 'parameters') else {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string", "minLength": 1},
                "scope": {"type": "string", "enum": ["memory", "docs", "all"]},
                "k": {"type": "integer", "description": "Number of results"},
            },
            "required": ["query"],
        }

    @property
    def read_only(self) -> bool:
        return True

    def __init__(self, workspace: Path, memory_store: MemoryStore | None = None, max_results: int = 5):
        self._inner = MemorySearchTool(workspace, memory_store, max_results)

    async def execute(self, query: str, scope: str = "all", k: int | None = None) -> str:
        """Execute search in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self._inner.execute,
            query,
            scope,
            k,
        )

    def invalidate_index(self) -> None:
        """Invalidate the underlying index."""
        self._inner.invalidate_index()
