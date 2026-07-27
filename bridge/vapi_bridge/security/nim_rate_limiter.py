"""Rate limiting for NIM API calls.

Implements token bucket rate limiting to prevent abuse and control costs.
"""
from __future__ import annotations

import time
import logging
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """Rate limit rule configuration."""
    window_seconds: int
    max_calls: int


class NIMRateLimiter:
    """Token bucket rate limiter for NIM API calls."""

    def __init__(self):
        # Per-device rate tracking
        self._device_calls: defaultdict[str, list] = defaultdict(list)

        # Rate limit rules
        self._rules = {
            "burst": RateLimitRule(window_seconds=60, max_calls=10),
            "sustained": RateLimitRule(window_seconds=3600, max_calls=100),
            "daily": RateLimitRule(window_seconds=86400, max_calls=1000),
        }

        # Fleet-wide tracking
        self._fleet_calls: list = []
        self._fleet_limit = 10000  # per day

    def check_rate_limit(self, device_id: str) -> tuple[bool, Optional[str]]:
        """Check if a device is within rate limits."""
        now = time.time()

        # Check per-device limits
        for rule_name, rule in self._rules.items():
            # Clean old calls
            self._device_calls[device_id] = [
                ts for ts in self._device_calls[device_id]
                if now - ts < rule.window_seconds
            ]

            # Check limit
            if len(self._device_calls[device_id]) >= rule.max_calls:
                log.warning(
                    f"Rate limit exceeded for device {device_id}: "
                    f"{rule_name} ({len(self._device_calls[device_id])}/{rule.max_calls})"
                )
                return False, rule_name

        # Check fleet-wide limit
        self._fleet_calls = [ts for ts in self._fleet_calls if now - ts < 86400]
        if len(self._fleet_calls) >= self._fleet_limit:
            log.warning(f"Fleet-wide rate limit exceeded: {len(self._fleet_calls)}/{self._fleet_limit}")
            return False, "fleet"

        # Record this call
        self._device_calls[device_id].append(now)
        self._fleet_calls.append(now)

        return True, None

    def get_device_stats(self, device_id: str) -> dict:
        """Get rate limit statistics for a device."""
        now = time.time()
        stats = {}

        for rule_name, rule in self._rules.items():
            recent_calls = [
                ts for ts in self._device_calls[device_id]
                if now - ts < rule.window_seconds
            ]
            stats[rule_name] = {
                "calls": len(recent_calls),
                "limit": rule.max_calls,
                "window_seconds": rule.window_seconds
            }

        return stats