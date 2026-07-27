"""API key lifecycle management with automatic rotation.

Provides secure API key generation, rotation, and revocation
for NIM integration with hardware-bound storage support.
"""
from __future__ import annotations

import secrets
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict
from enum import Enum

log = logging.getLogger(__name__)


class KeyStatus(Enum):
    """Status of an API key version."""
    ACTIVE = "active"
    ROTATING = "rotating"
    REVOKED = "revoked"
    COMPROMISED = "compromised"


@dataclass
class APIKeyVersion:
    """Metadata for an API key version."""
    version: str
    key: str
    status: KeyStatus
    created_at: float
    expires_at: float
    last_used_at: Optional[float] = None


class APIKeyManager:
    """Manages API key lifecycle with automatic rotation."""

    def __init__(self, env: str = "prod"):
        self.env = env
        self.keys: Dict[str, APIKeyVersion] = {}
        self.rotation_interval_days = 90
        self.grace_period_days = 7

    def generate_key(self, purpose: str) -> str:
        """Generate a new API key with version tracking."""
        version = f"v{int(time.time())}"
        key = secrets.token_urlsafe(32)  # 32-byte entropy

        key_version = APIKeyVersion(
            version=version,
            key=key,
            status=KeyStatus.ACTIVE,
            created_at=time.time(),
            expires_at=time.time() + (self.rotation_interval_days * 86400)
        )

        key_id = f"NIM_{self.env.upper()}_{purpose.upper()}_{version}"
        self.keys[key_id] = key_version

        log.info(f"Generated new API key: {key_id}")
        return key_id

    def rotate_key(self, key_id: str) -> Optional[str]:
        """Rotate an existing key with grace period overlap."""
        if key_id not in self.keys:
            log.error(f"Key not found for rotation: {key_id}")
            return None

        old_key = self.keys[key_id]

        # Mark old key as rotating
        old_key.status = KeyStatus.ROTATING
        old_key.expires_at = time.time() + (self.grace_period_days * 86400)

        # Generate new key
        purpose = key_id.split("_")[2].lower()
        new_key_id = self.generate_key(purpose)

        log.info(f"Rotated key: {key_id} -> {new_key_id}")
        return new_key_id

    def revoke_key(self, key_id: str, reason: str = "manual") -> bool:
        """Immediately revoke a key."""
        if key_id not in self.keys:
            return False

        self.keys[key_id].status = KeyStatus.REVOKED
        log.warning(f"Revoked key: {key_id}, reason: {reason}")
        return True

    def get_active_key(self, purpose: str) -> Optional[str]:
        """Get the active key for a purpose."""
        # Find keys matching purpose
        matching_keys = [
            (k_id, k_v) for k_id, k_v in self.keys.items()
            if k_id.startswith(f"NIM_{self.env.upper()}_{purpose.upper()}")
        ]

        # Return active key
        for key_id, key_version in matching_keys:
            if key_version.status == KeyStatus.ACTIVE:
                if time.time() < key_version.expires_at:
                    return key_version.key
                else:
                    # Auto-expire
                    key_version.status = KeyStatus.REVOKED

        return None

    def check_rotation_needed(self) -> list:
        """Check which keys need rotation."""
        needs_rotation = []
        now = time.time()

        for key_id, key_version in self.keys.items():
            if key_version.status == KeyStatus.ACTIVE:
                # Rotate if 80% of lifetime elapsed
                lifetime = key_version.expires_at - key_version.created_at
                age = now - key_version.created_at
                if age > (lifetime * 0.8):
                    needs_rotation.append(key_id)

        return needs_rotation