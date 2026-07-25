#!/usr/bin/env python3
"""RWM L0 post-session check — one command, run it right after a capture session.

Why this exists: RWM is fail-open by design, so an RWM error can never break the
stop path. The cost of that choice is that "RWM wrote a valid chain" and "RWM
silently did nothing" look identical from the play side. This closes that gap.

    python scripts/rwm_post_session_check.py                # newest archived session
    python scripts/rwm_post_session_check.py --label warzone_t66b4
    python scripts/rwm_post_session_check.py --session-dir retina_kf_archive/<dir>

Checks, in order of what matters:
  1. Did RWM run at all?                    (honest-null if disabled/skipped)
  2. Third-party re-verify from disk bytes  (THE claim: recompute + verify_session_chain)
  3. Originals byte-identical               (vs the tier-1 manifest.json _archive_ring wrote)
  4. Locator decodable on REAL frames       (expected to be imperfect on run 1 — see below)
  5. Geometry / block_px ratio              (RWM_BLOCK_PX=32 is untuned for real crops)
  6. Content diversity (unique panel SHA-256 ratio) — freezes / static rings

Exit 0 = every load-bearing check passed. Exit 1 = a real failure. Exit 2 = RWM
didn't run (not a failure — just tells you which case you're in).

Check 4 is DIAGNOSTIC, not pass/fail. Palette and block_px calibration are
D7-deferred; the first real-frame run is meant to MEASURE decode quality, not
assert it. A failed decode here is data for the next round, not a broken build.

Check 6 is DIAGNOSTIC by default (INFO) so a frozen ring can still pass chain
math — but unique==1 is called out as FROZEN_RING. Pass --strict-diversity to
promote unique_ratio==0 (or unique==1) to a load-bearing FAIL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "bridge"))

OK, BAD, INFO, SKIP = "PASS", "FAIL", "INFO", "SKIP"


def _line(status: str, title: str, detail: str = "") -> None:
    print(f"  [{status:4}] {title}" + (f"\n         {detail}" if detail else ""))


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _newest_session() -> Path | None:
    root = _REPO / "retina_kf_archive"
    if not root.is_dir():
        return None
    dirs = [d for d in root.iterdir() if d.is_dir()]
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def main() -> int:
    ap = argparse.ArgumentParser(description="RWM L0 post-session verification")
    ap.add_argument("--session-dir", default=None, help="explicit archive dir")
    ap.add_argument("--label", default=None, help="match newest dir starting with this label")
    ap.add_argument(
        "--strict-diversity",
        action="store_true",
        help="FAIL when original panel content is frozen (unique SHA-256 count == 1)",
    )
    a = ap.parse_args()

    if a.session_dir:
        dst = Path(a.session_dir)
        if not dst.is_absolute():
            dst = _REPO / dst
    elif a.label:
        root = _REPO / "retina_kf_archive"
        cands = sorted((d for d in root.glob(f"{a.label}*") if d.is_dir()),
                       key=lambda d: d.stat().st_mtime)
        dst = cands[-1] if cands else None
    else:
        dst = _newest_session()

    print("\nRWM L0 post-session check")
    print("=" * 72)
    if dst is None or not dst.is_dir():
        _line(BAD, "no archived session found", "retina_kf_archive/ is empty or missing")
        return 1
    print(f"  session: {dst.name}\n")

    originals = sorted(dst.glob("panel_*.png"))
    chain_p = dst / "rwm_manifest_chain.json"

    # --- 1. did RWM run at all? -------------------------------------------------------
    if not chain_p.is_file():
        _line(SKIP, "RWM did not run for this session", (
            "No rwm_manifest_chain.json. Either RWM_L0_DAEMON_ENABLED was unset, "
            "RWM_DEVICE_ID_HEX was unset (device_id is never fabricated), the ring was "
            "empty, or RWM failed fail-open. Check the daemon stop output for a "
            "'[daemon] RWM:' line — it always says which."))
        print()
        return 2
    rec = json.loads(chain_p.read_text(encoding="utf-8"))
    _line(OK, "RWM ran", f"{len(rec.get('frames', []))} frames chained, "
                         f"schema={rec.get('schema')} candidate={rec.get('candidate')}")

    failures = 0

    # --- 2. THE claim: third-party re-verify from disk bytes alone --------------------
    from vapi_bridge.retina_capture_manifest import verify_session_chain
    frames, missing = [], []
    for f in rec["frames"]:
        p = dst / f["file"]
        if not p.is_file():
            missing.append(f["file"])
            continue
        frames.append((hashlib.sha256(p.read_bytes()).digest(), f["ts_ns"]))

    if missing:
        _line(BAD, "marked frames missing from disk", f"{len(missing)} absent, e.g. {missing[:2]}")
        failures += 1
    else:
        recomputed_ok = all(
            hashlib.sha256((dst / f["file"]).read_bytes()).hexdigest() == f["frame_hash_hex"]
            for f in rec["frames"])
        chain = [bytes.fromhex(h) for h in rec["chain_hex"]]
        verified = verify_session_chain(rec["session_id"], rec["device_id_hex"],
                                        rec["genesis_ts_ns"], frames, chain)
        if recomputed_ok and verified:
            _line(OK, "third-party re-verify from disk bytes alone", (
                "recomputed every frame hash from the archived marked/ files and the "
                "chain verifies — this is the property the whole design exists for"))
        else:
            _line(BAD, "third-party re-verify FAILED",
                  f"per-frame hashes match={recomputed_ok}  chain verifies={verified}")
            failures += 1

    # --- 3. originals untouched (vs the tier-1 manifest _archive_ring already wrote) ---
    tier1 = dst / "manifest.json"
    if not tier1.is_file():
        _line(INFO, "no tier-1 manifest.json", "cannot prove originals unmodified this run")
    else:
        t1 = json.loads(tier1.read_text(encoding="utf-8"))
        drift = [e["file"] for e in t1.get("files", [])
                 if (dst / e["file"]).is_file() and _sha(dst / e["file"]) != e["sha256"]]
        if drift:
            _line(BAD, "ORIGINAL ARCHIVE FRAMES WERE MODIFIED", (
                f"{len(drift)} differ from the tier-1 manifest, e.g. {drift[:3]}. "
                "RWM is sidecar-only — it must never mutate originals. This is a rail violation."))
            failures += 1
        else:
            _line(OK, "originals byte-identical",
                  f"all {len(t1.get('files', []))} match the tier-1 archive manifest (sidecar held)")

    # --- 4. DIAGNOSTIC: locator decode on real frames ---------------------------------
    try:
        import cv2

        from vapi_bridge.retina_witness_mark import (compute_locator_payload,
                                                     decode_mark_from_frames)
        loc = rec.get("locator", {})
        blk = int(loc.get("block_px", 32))
        marked = [cv2.imread(str(dst / f["file"]), cv2.IMREAD_COLOR) for f in rec["frames"]]
        marked = [m for m in marked if m is not None]
        from vapi_bridge.retina_witness_mark import encode_mark_symbols
        expected = compute_locator_payload(bytes.fromhex(loc["session_id_hash_8b_hex"]),
                                           int(loc.get("checkpoint_index", 0)))
        # One full mark cycle is 2 preamble + payload*repeat frames (146 at L0). A session
        # that archived fewer crops than that CANNOT decode -- structural, not a defect --
        # so report it as its own case rather than letting it read as a decode failure.
        cycle = len(encode_mark_symbols(expected))
        if len(marked) < cycle:
            _line(INFO, "too few frames to decode the locator", (
                f"{len(marked)} marked frames < {cycle} needed for one full mark cycle. "
                "Structural, not a defect: the payload repeats across frames and a short "
                "session never completes a cycle. Says nothing about decode quality."))
        else:
            decoded = decode_mark_from_frames(marked, corner=loc.get("corner", "bottom-right"),
                                              block_px=blk)
            if decoded is None:
                _line(INFO, "locator did NOT decode on real frames", (
                    "EXPECTED on the first real-frame run and NOT a failure — palette and "
                    "block_px calibration are D7-deferred, and RWM_BLOCK_PX=32 is untuned "
                    "for real capture geometry. This is the measurement the live-rig pass "
                    "exists to produce. Record it; do not tune mid-session."))
            elif decoded == expected:
                _line(OK, "locator decoded correctly on real frames",
                      f"payload round-trips through real capture-card output ({len(marked)} frames)")
            else:
                _line(INFO, "locator decoded but payload MISMATCH",
                      f"got {decoded.hex()[:24]}… expected {expected.hex()[:24]}… — record for next round")
    except ImportError:
        _line(SKIP, "cv2 unavailable — decode diagnostic skipped")
    except Exception as e:  # noqa: BLE001 — diagnostic must never fail the check
        _line(INFO, "decode diagnostic errored (non-fatal)", repr(e)[:120])

    # --- 5. geometry vs block_px ------------------------------------------------------
    try:
        import cv2
        if originals:
            img = cv2.imread(str(originals[0]), cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                blk = int(rec.get("locator", {}).get("block_px", 32))
                pct = 100.0 * blk / min(h, w)
                _line(INFO, "crop geometry vs block_px",
                      f"{w}x{h}; block_px={blk} = {pct:.1f}% of short edge "
                      f"({'plausible' if pct >= 4 else 'possibly too small to decode reliably'})")
    except Exception:  # noqa: BLE001
        pass

    # --- 6. content diversity (frozen-ring detector) ---------------------------------
    # Chain math can PASS on a static ring (every panel byte-identical). That is still
    # a valid integrity proof of the pipeline, but it is NOT diverse live play.
    # Spot-check protocol (R09/R10): measure unique SHA-256 of original panel_*.png.
    from vapi_bridge.rwm_panel_diversity import panel_content_stats

    if originals:
        stats = panel_content_stats(originals)
        unique, n, ratio = stats["unique"], stats["n"], stats["ratio"]
        if stats["frozen"]:
            detail = (
                f"unique_content={unique}/{n} (ratio={ratio:.1%}) — FROZEN_RING: all "
                f"original panels share one content hash. Chain may still verify; do not "
                f"cite as multi-frame live play. Eye-check capture source / OBS freeze."
            )
            if a.strict_diversity:
                _line(BAD, "content diversity FROZEN_RING", detail)
                failures += 1
            else:
                _line(INFO, "content diversity FROZEN_RING", detail)
        elif ratio < 0.10:
            _line(INFO, "content diversity low", (
                f"unique_content={unique}/{n} (ratio={ratio:.1%}) — mostly repeated "
                f"frames (menu/static/ring mix). Chain integrity independent."
            ))
        else:
            _line(OK, "content diversity", (
                f"unique_content={unique}/{n} (ratio={ratio:.1%}) — non-trivial "
                f"frame variety"
            ))
    else:
        _line(INFO, "content diversity skipped", "no original panel_*.png")

    print()
    if failures:
        print(f"  RESULT: {failures} load-bearing check(s) FAILED — this is a finding.\n")
        return 1
    print("  RESULT: all load-bearing checks passed."
          "  (INFO lines are measurements, not failures.)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
