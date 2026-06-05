"""Outbound delivery helpers (message burst, etc.)."""

from nanobot.delivery.burst import (
    BurstDelivery,
    maybe_burst_parts,
    plan_burst_delivery,
    random_burst_delay_s,
)

__all__ = [
    "BurstDelivery",
    "maybe_burst_parts",
    "plan_burst_delivery",
    "random_burst_delay_s",
]
