"""BM25 full-text search index — pure Python implementation, no external dependencies."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


class BM25Index:
    """
    Lightweight BM25 index for local document search.

    Features:
    - Pure Python, no external dependencies
    - Scans workspace for .md and .txt files
    - BM25 scoring for relevance ranking
    - Simple tokenization with Chinese support
    """

    def __init__(
        self,
        workspace: Path,
        k1: float = 1.5,
        b: float = 0.75,
        min_doc_length: int = 10,
    ):
        self.workspace = workspace
        self.k1 = k1
        self.b = b
        self.min_doc_length = min_doc_length

        # Index data
        self._documents: dict[str, list[str]] = {}  # path -> tokens
        self._doc_lengths: dict[str, int] = {}
        self._df: Counter = Counter()  # document frequency
        self._num_docs: int = 0
        self._avgdl: float = 0.0
        self._indexed_paths: set[str] = set()

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization: lowercase, extract alphanumeric tokens."""
        # Handle Chinese characters (treat each as a token)
        # Handle English words
        tokens = []
        for chunk in re.split(r'([\u4e00-\u9fff]|[a-zA-Z0-9]+)', text.lower()):
            chunk = chunk.strip()
            if len(chunk) >= 2:  # Skip single chars
                tokens.append(chunk)
        return tokens

    def _read_document(self, path: Path) -> str | None:
        """Read a document, handling encoding issues."""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                return path.read_text(encoding="gbk")
            except Exception:
                return None
        except Exception:
            return None

    def index_documents(
        self,
        extensions: list[str] | None = None,
        max_files: int = 1000,
        exclude_dirs: set[str] | None = None,
    ) -> int:
        """
        Index all documents in workspace.

        Args:
            extensions: File extensions to index (default: .md, .txt)
            max_files: Maximum number of files to index
            exclude_dirs: Directory names to exclude (default: .git, .obsidian, node_modules)

        Returns:
            Number of documents indexed
        """
        if extensions is None:
            extensions = [".md", ".txt"]
        if exclude_dirs is None:
            exclude_dirs = {".git", ".obsidian", "node_modules", ".claude", ".trash"}

        indexed = 0
        self._documents.clear()
        self._doc_lengths.clear()
        self._df.clear()
        self._indexed_paths.clear()

        total_tokens = 0

        for path in self.workspace.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in extensions:
                continue
            if any(excluded in path.parts for excluded in exclude_dirs):
                continue
            if indexed >= max_files:
                break

            content = self._read_document(path)
            if content is None:
                continue

            tokens = self._tokenize(content)
            if len(tokens) < self.min_doc_length:
                continue

            rel_path = str(path.relative_to(self.workspace))
            self._documents[rel_path] = tokens
            self._doc_lengths[rel_path] = len(tokens)
            total_tokens += len(tokens)

            # Update document frequency
            unique_terms = set(tokens)
            for term in unique_terms:
                self._df[term] += 1

            self._indexed_paths.add(rel_path)
            indexed += 1

        self._num_docs = indexed
        self._avgdl = total_tokens / max(indexed, 1)

        return indexed

    def search(self, query: str, k: int = 5) -> list[tuple[str, float, str]]:
        """
        Search for relevant documents.

        Args:
            query: Search query
            k: Number of top results to return

        Returns:
            List of (path, score, snippet) tuples, sorted by relevance
        """
        if not self._documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[str, float, str]] = []

        for path, doc_tokens in self._documents.items():
            score = self._bm25_score(doc_tokens, query_tokens)
            if score > 0:
                # Extract snippet (first 200 chars of content)
                snippet = " ".join(doc_tokens[:100])
                scores.append((path, score, snippet))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:k]

    def _bm25_score(self, doc_tokens: list[str], query_tokens: list[str]) -> float:
        """Calculate BM25 score for a document given query tokens."""
        if not doc_tokens or not query_tokens:
            return 0.0

        doc_len = len(doc_tokens)
        doc_freq = Counter(doc_tokens)

        score = 0.0
        N = self._num_docs

        for term in query_tokens:
            if term not in doc_freq:
                continue

            tf = doc_freq[term]
            df = self._df.get(term, 0)

            if df == 0:
                continue

            # IDF with base e (smoothed)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1)

            # TF normalization
            tf_norm = (tf * (self.k1 + 1)) / (
                tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avgdl, 1))
            )

            score += idf * tf_norm

        return score

    def get_document(self, path: str) -> str | None:
        """Get raw document content by relative path."""
        full_path = self.workspace / path
        return self._read_document(full_path)

    @property
    def num_documents(self) -> int:
        """Number of indexed documents."""
        return self._num_docs

    @property
    def indexed_paths(self) -> list[str]:
        """List of indexed file paths."""
        return list(self._indexed_paths)
