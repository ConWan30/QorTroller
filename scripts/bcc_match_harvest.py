#!/usr/bin/env python3
"""BCC Match harvest runner (A1-b v0, NONE-only).

Composes a session's assertion-plane surfaces (a PoSP record + optional deferred/live KAS)
into a MatchPresenceArtifact and, IF BCC_MATCH_ENABLED, appends it to the sealed bcc_match/
lane. Fail-OPEN host: a harvest error never breaks anything (advisory corpus). The GATE is
fail-CLOSED inside build_match_presence_artifact (any admission miss -> no write).

v0 is NONE-only (F-A1b-AUDIT-1): rows carry feature_contract.name="NONE" — assertion-plane
only, no L4 attachment (that returns in artifact-v1).

Coherence numerator / denominator (§6.2):
  - with --deferred: authored = deferred_authored, eligible = authored + deferred_observed
  - else:            --authored and --eligible are REQUIRED (no silent 1.0 for live-only)

Env:
    BCC_MATCH_ENABLED         default false — dormant unless set (1/true/yes)
    BCC_MATCH_COHERENCE_FLOOR default 0.50 (pre-registered; do not retune in a harvest run)
    BCC_MATCH_OUT_DIR         default bcc_match

Usage:
    BCC_MATCH_ENABLED=1 python scripts/bcc_match_harvest.py \
        --posp audits/posp_record_match14_rp_option_b_...json \
        --deferred audits/kas_deferred_record_match14_...json \
        [--archive retina_kf_archive/match14_...] [--transport RP]

Exit 0 = artifact built (and harvested if enabled); 1 = admission rejected; 2 = I/O error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.bcc_match import (
    BCCMatchConfig,
    DEFAULT_COHERENCE_FLOOR,
    MatchHarvester,
    build_match_presence_artifact,
)


def _envbool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser(description="BCC Match harvest runner (A1-b v0, NONE-only)")
    ap.add_argument("--posp", required=True, help="PoSP record JSON (audits/posp_record_*.json)")
    ap.add_argument("--deferred", default=None, help="deferred-attestation record JSON (optional)")
    ap.add_argument("--kas", default=None, help="live KAS record JSON (optional; else PoSP-embedded)")
    ap.add_argument("--archive", default=None, help="archive dir to record as archive_manifest_dir")
    ap.add_argument("--transport", default=None, choices=["USB", "RP", "UNKNOWN"])
    ap.add_argument("--authored", type=int, default=None, help="authored clusters (if no --deferred)")
    ap.add_argument("--eligible", type=int, default=None, help="eligible clusters (if no --deferred)")
    ap.add_argument("--out-dir", default=os.environ.get("BCC_MATCH_OUT_DIR", "bcc_match"))
    a = ap.parse_args()

    try:
        posp = _load(a.posp)
    except Exception as e:                       # noqa: BLE001 — I/O boundary, fail with exit 2
        print(f"ERROR: cannot load PoSP record {a.posp!r}: {e}", file=sys.stderr)
        return 2

    deferred = None
    if a.deferred:
        try:
            deferred = _load(a.deferred)
        except Exception as e:                   # noqa: BLE001
            print(f"ERROR: cannot load deferred record {a.deferred!r}: {e}", file=sys.stderr)
            return 2

    # live KAS: explicit file wins; else the summary the PoSP record embeds
    kas = None
    if a.kas:
        try:
            kas = _load(a.kas)
        except Exception as e:                   # noqa: BLE001
            print(f"ERROR: cannot load KAS record {a.kas!r}: {e}", file=sys.stderr)
            return 2
    else:
        kas = posp.get("kas")

    # coherence numerator / denominator
    if deferred is not None:
        authored = int(deferred.get("deferred_authored") or 0)
        eligible = authored + int(deferred.get("deferred_observed") or 0)
    elif a.authored is not None and a.eligible is not None:
        authored, eligible = a.authored, a.eligible
    else:
        print("ERROR: coherence needs --deferred OR both --authored and --eligible "
              "(no silent 1.0 for live-only)", file=sys.stderr)
        return 2

    # let the runner supply the archive dir it knows (real PoSP records don't embed one)
    if a.archive:
        posp.setdefault("archive", {})
        posp["archive"]["dir"] = a.archive

    floor = float(os.environ.get("BCC_MATCH_COHERENCE_FLOOR", DEFAULT_COHERENCE_FLOOR))
    artifact, reasons = build_match_presence_artifact(
        session_id=posp.get("session_id"), session_display=posp.get("session_display"),
        device_id=posp.get("device_id"), span_ms=posp.get("span_ms"),
        posp=posp, kas=kas, deferred=deferred,
        authored_clusters=authored, eligible_clusters=eligible,
        transport=a.transport, coherence_floor=floor)

    if artifact is None:
        print(json.dumps({"built": False, "admission_rejected": True, "reasons": reasons}, indent=2))
        return 1

    enabled = _envbool("BCC_MATCH_ENABLED")
    summary = {
        "built": True,
        "session_id": artifact["session_id"],
        "session_display": artifact["session_display"],
        "coherence": artifact["admission"]["coherence_fraction"],
        "coherence_floor": floor,
        "authorship_tier": artifact["admission"]["authorship_tier"],
        "feature_contract": artifact["feature_contract"]["name"],   # always NONE in v0
        "bcc_match_enabled": enabled,
    }

    if enabled:
        # fail-OPEN host: a harvest error is reported, never raised past the runner
        try:
            h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=a.out_dir, coherence_floor=floor))
            rec = h.record(artifact)
            summary["harvested"] = rec is not None
            summary["seq"] = (rec or {}).get("seq")
            summary["chain"] = h.status()
        except Exception as e:                   # noqa: BLE001 — advisory corpus, never fatal
            summary["harvested"] = False
            summary["harvest_error"] = str(e)
    else:
        summary["harvested"] = False
        summary["note"] = "dormant — set BCC_MATCH_ENABLED=1 to accumulate"

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
