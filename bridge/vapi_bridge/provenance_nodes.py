"""Canonical provenance DAG node identifiers (shared across curator + operator API)."""
from __future__ import annotations

import hashlib


def poac_record_node_id(record_hash: str) -> str:
    """Stable DAG node id for a PoAC record (grind provenance parent anchor)."""
    return "sha256:" + hashlib.sha256(f"poac_record:{record_hash}".encode()).hexdigest()


def register_retina_provenance_node(
    store: object,
    row_id: int,
    record_hash_hex: str,
    commitment_hex: str,
) -> None:
    """Synchronous PERCEPTION_BINDING child at persist time (fail-open)."""
    if not commitment_hex or not hasattr(store, "insert_provenance_node"):
        return
    try:
        node_id = "sha256:" + hashlib.sha256(
            f"retina_event_log:{row_id}".encode()
        ).hexdigest()
        parent_id = poac_record_node_id(record_hash_hex) if record_hash_hex else None
        store.insert_provenance_node({
            "node_id": node_id,
            "node_type": "RETINA_STATE_COMMITMENT",
            "source_table": "retina_event_log",
            "source_row_id": row_id,
            "source_hash": commitment_hex,
            "parent_node_id": parent_id,
            "edge_type": "PERCEPTION_BINDING",
            "phase_produced": 192,
            "player_id": None,
            "on_chain_ref": commitment_hex,
        })
    except Exception:
        pass  # fail-open: curator poll remains backup
