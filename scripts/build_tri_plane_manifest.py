#!/usr/bin/env python3
"""TPF-1 F1 - build + verify the tri-plane session manifest for a match.

Federates the assertion + observation plane (the PoSP record) and the meaning plane
(the WMP bundle) into one session object, bound by reference, honest about the join
status. `--attested` records the developer_self operator attestation that both
artifacts are the same session (the WMP bundle carries no session_id to prove it
cryptographically yet - see the F3 path). Reads only; no chain, no spend. ASCII-only.

  python scripts/build_tri_plane_manifest.py --attested [--out audits/tri_plane_manifest_m17.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from l9_presence.tri_plane_manifest import build_tri_plane_manifest, verify_tri_plane_manifest

_POSP = os.path.join(_REPO, "audits", "posp_record_match17_rp_fixb3_2026-07-08.json")
_WMP = os.path.join(_REPO, "wmp_corpus_real", "wmp_corpus.jsonl")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="TPF-1 F1 tri-plane session manifest")
    ap.add_argument("--attested", action="store_true",
                    help="record the developer_self attestation that both artifacts are this session")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    posp = json.load(open(_POSP, encoding="utf-8"))
    wmp = json.loads(open(_WMP, encoding="utf-8").read().splitlines()[0])
    m = build_tri_plane_manifest(posp, wmp, attested_same_session=a.attested,
                                 generated_at="2026-07-11")
    res = verify_tri_plane_manifest(m, posp=posp, wmp_bundle=wmp)

    p = m["planes"]
    print("=" * 78)
    print("  TPF-1 F1 - TRI-PLANE SESSION MANIFEST (one match, three planes, federated)")
    print("=" * 78)
    print(f"  session_id : {str(m['session_id'])[:52]}")
    print("-" * 78)
    print(f"  ASSERTION   posp   verdict={p['assertion']['verdict']}  "
          f"kas_root={str(p['assertion']['kas_session_root'])[:16]}...")
    print(f"  OBSERVATION posp   retina_perception_root={str(p['observation']['retina_perception_root'])[:16]}...")
    print(f"  MEANING     wmp    bundle_hash={str(p['meaning']['bundle_hash'])[:16]}...  "
          f"gamer={str(p['meaning']['consent_gamer_address'])[:12]}...")
    print("-" * 78)
    js = m["join_status"]
    print(f"  join: assertion<->observation = {js['assertion_observation']}   "
          f"meaning<->session = {js['meaning_session']}")
    print(f"  F3 hard-join path: {m['hard_join_path_F3'][:64]}...")
    print("-" * 78)
    for c in res["checks"]:
        print(f"  [{'OK ' if c['ok'] else 'FAIL':4}] {c['name']}")
    print(f"  VERIFY: {'ok' if res['ok'] else 'FAILED'}   (federation, not conflation)")
    if a.out:
        with open(os.path.join(_REPO, a.out) if not os.path.isabs(a.out) else a.out,
                  "w", encoding="utf-8") as f:
            json.dump(m, f, indent=2)
        print(f"  wrote {a.out}")
    print("=" * 78)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
