#!/usr/bin/env python3
"""TRA-1 T2 demo - QorTroller multi-modal fusion in Trio Retina's WorldState schema.

Builds a synthetic fused WorldState: an on-screen entity (bbox + a model-tagged visual vec)
alongside the certified controller (a phi-quantized input-space `locus`, no biometric, no
latent), validates it against the standard + both honesty rails (separation law + biometric
floor), and writes the example artifact. ASCII-only (cp1252-safe). No card, no network.
"""
from __future__ import annotations

import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from bridge.vapi_bridge.retina_worldstate_std import (
    make_worldstate, make_entity, controller_entity, make_vec, validate_worldstate,
)


def build() -> dict:
    # OBSERVATION (video): an on-screen enemy the vision model detected, with a ReID latent.
    enemy = make_entity(
        "enemy_7", "person", bbox=[812, 430, 902, 640],
        vec=make_vec("osnet-reid", 4, dtype="fp32", values=[0.11, 0.22, 0.33, 0.44]),
    )
    # FUSION (controller): the certified pad as a FIELD SUBJECT - its exportable state is a
    # point in INPUT space (coarse right-stick sector), NOT a pixel box and NOT a latent.
    pad = controller_entity("edge_pad", input_locus=[0.62, 0.05])
    return make_worldstate(
        src="retina_m17", t=1783550435.0, frame=524,
        entities=[enemy, pad],
        scene=make_vec("v-jepa2-vitl", 1024, dtype="fp16", ref="vec://scene_m17"),
    )


def main() -> int:
    ws = build()
    problems = validate_worldstate(ws)
    assert problems == [], problems
    out = os.path.join(_REPO, "audits", "tra1-t2-fusion-worldstate-example.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(ws, f, indent=2)
    print("=" * 72)
    print("TRA-1 T2 - fused WorldState: video (bbox + visual vec) + controller (locus)")
    print("=" * 72)
    print(json.dumps(ws, indent=2))
    print("-" * 72)
    print("rails: separation law (no verdict) + biometric floor (moat absent) -> both PASS")
    print("audio: dropped by principle (BIPA/GDPR sovereignty)")
    print("wrote", os.path.relpath(out, _REPO).replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
