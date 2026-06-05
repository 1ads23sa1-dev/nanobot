"""Outbound delivery helpers (message burst, etc.)."""

from nanobot.delivery.burst import maybe_burst_parts, random_burst_delay_s

__all__ = ["maybe_burst_parts", "random_burst_delay_s"]
