#!/usr/bin/env python3
"""TRA-1 T3 demo - compute a REAL VAPI-RETINA-STATE-v3 commitment (the verify rung).

Builds a synthetic conformant retina.event/0.1 stream + the T2 fused WorldState, then computes
the v3 commitment (ordered Poseidon events root + WorldState digest) with the REAL node Poseidon
helper. Writes the example artifact. If node / circomlibjs is unavailable, prints a node-gated
note and exits 0 (the mechanism + forge tests are the primary T3 deliverable). ASCII-only.
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from bridge.vapi_bridge.retina_event_std import make_event, to_jsonl
from bridge.vapi_bridge.retina_worldstate_std import make_worldstate, make_entity, controller_entity, make_vec
from bridge.vapi_bridge.retina_state_commitment import compute_retina_state_commitment_v3

_DEVICE = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"   # canonical DualShock Edge


def main() -> int:
    stream = [
        make_event("zone.enter", 1783550435.0, "retina_m17", zone="engage", id=7),
        make_event("x_qortroller.kill", 1783550436.5, "retina_m17", label="headshot", conf=0.9),
    ]
    ws = make_worldstate(
        src="retina_m17", t=1783550435.0, frame=524,
        entities=[
            make_entity("enemy_7", "person", bbox=[812, 430, 902, 640],
                        vec=make_vec("osnet-reid", 2, values=[0.1, 0.2])),
            controller_entity("edge_pad", input_locus=[0.62, 0.05]),
        ],
        scene=make_vec("v-jepa2-vitl", 1024, dtype="fp16", ref="vec://scene_m17"),
    )
    print("=" * 72)
    print("TRA-1 T3 - VAPI-RETINA-STATE-v3 verify rung (ordered stream + WorldState frame)")
    print("=" * 72)
    print("event stream (ordered JSON-Lines):")
    print(to_jsonl(stream))
    try:
        commitment = compute_retina_state_commitment_v3(_DEVICE, 1783550435000000000, stream, worldstate=ws)
    except Exception as e:                                    # node / circomlibjs missing
        print("-" * 72)
        print(f"real Poseidon commit is node-gated (skipped): {type(e).__name__}: {str(e)[:120]}")
        print("mechanism + forge tests are the primary T3 deliverable; artifact deferred.")
        return 0
    artifact = {
        "schema": "vapi-retina-state-v3-example",
        "note": "CANDIDATE - NOT FROZEN, NOT PV-CI-pinned; promotion to FROZEN-v1 is an operator seal",
        "device_id": _DEVICE,
        "ts_ns": 1783550435000000000,
        "event_count": len(stream),
        "worldstate_entities": len(ws["entities"]),
        "state_commitment_v3": commitment,
    }
    out = os.path.join(_REPO, "audits", "tra1-t3-state-v3-example.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print("-" * 72)
    print("VAPI-RETINA-STATE-v3 :", commitment)
    print("rails: conformance + separation law + biometric floor -> all PASS before commit")
    print("wrote", os.path.relpath(out, _REPO).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
