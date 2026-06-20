"""Canonical provenance DAG node identifiers (shared across curator + operator API)."""
from __future__ import annotations

import hashlib


def poac_record_node_id(record_hash: str) -> str:
    """Stable DAG node id for a PoAC record (grind provenance parent anchor)."""
    return "sha256:" + hashlib.sha256(f"poac_record:{record_hash}".encode()).hexdigest()
