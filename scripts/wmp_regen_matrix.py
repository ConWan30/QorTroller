#!/usr/bin/env python3
"""WMP Phase-2 INC-0/INC-3 -- regenerate a session's SanitizedReplayMatrix from a bridge DB.

The M17 real proof's sanitizedTraceRoot was computed over a matrix that was never saved; this
tool re-derives it deterministically: frame_checkpoints (ordered by id ASC = capture order) ->
ReplayPreProcessor.process_session (the UNTOUCHED Arc 5 phi) -> matrix JSON in the exact shape
compute_inputs_replay_proof.js consumes. The PoAC chain root regenerates too (the DB's 463
record_hash rows are the Merkle leaves).

KILL-CHECK MODE (--expect-public): runs the Poseidon helper (--print-commitments) and compares
the recomputed sanitizedTraceRoot against the committed public inputs (index 1). Byte-match ->
exit 0 (determinism proven; safe to build the real bundle over this matrix). Mismatch -> exit 1
(phi non-determinism or DB drift -- STOP the promote, file the finding). Missing node/helper ->
exit 2 (incomplete env, never a silent pass).

  python scripts/wmp_regen_matrix.py --db C:/Users/Contr/.vapi/bridge_match17.db \
      --session-id match17_rp_fixb3 --out-private audits/wmp_m17_private_inputs.json \
      --expect-public audits/vhr_proof2_m17/public_m17_real.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "bridge"))

_HELPER = os.path.join(_REPO, "bridge", "vapi_bridge", "replay_proof_pipeline",
                       "zk_artifacts", "compute_inputs_replay_proof.js")


def load_frames_and_hashes(db_path: str):
    """frame_checkpoints ordered by id ASC (insertion == capture order — the determinism
    assumption the kill-check exists to prove). Returns (frames, record_hashes, n_rows)."""
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT frames_json, record_hash FROM frame_checkpoints ORDER BY id ASC").fetchall()
    con.close()
    frames: list = []
    hashes: list = []
    for fj, rh in rows:
        frames.extend(json.loads(fj))
        hashes.append(rh)
    return frames, hashes, len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate SanitizedReplayMatrix from a bridge DB")
    ap.add_argument("--db", required=True)
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--out-private", required=True,
                    help="private-inputs JSON for compute_inputs_replay_proof.js")
    ap.add_argument("--expect-public", default=None,
                    help="committed public.json — kill-check the recomputed sanitizedTraceRoot "
                         "against index 1")
    a = ap.parse_args()

    from vapi_bridge.replay_proof_pipeline.pre_processor import ReplayPreProcessor

    frames, record_hashes, n_rows = load_frames_and_hashes(a.db)
    print(f"  checkpoints          : {n_rows} rows -> {len(frames)} structural frames")
    m = ReplayPreProcessor().process_session(a.session_id, frames=frames,
                                             record_hashes=record_hashes)
    print(f"  matrix               : ticks={m.ticks} "
          f"(chL={len(m.stick_L_sector)} chR={len(m.stick_R_sector)} "
          f"tL={len(m.trigger_L_state)} tR={len(m.trigger_R_state)} "
          f"btn={len(m.button_mask)} imu={len(m.imu_gravity_sector)})")
    print(f"  poac_chain_root      : {m.poac_chain_root.hex()}")

    # Private-inputs JSON: sanitizedTraceRoot depends ONLY on `matrix`; the remaining required
    # fields are pass-throughs for the helper's other commitments — dummies are fine for the
    # kill-check and are replaced with real values at proof time (INC-5 uses the committed
    # proof, so they are never re-proven here).
    priv = {
        "humanityProbabilityWitness": "700",
        "humanityThreshold": "700",
        "vhpTokenId": "0",
        "sessionNonce": "0",
        "poacChainRoot": "0x" + m.poac_chain_root.hex(),
        "consentPolicyHash": "0",
        "matrix": {
            "ticks": m.ticks,
            "stick_L_sector": m.stick_L_sector.hex(),
            "stick_R_sector": m.stick_R_sector.hex(),
            "trigger_L_state": m.trigger_L_state.hex(),
            "trigger_R_state": m.trigger_R_state.hex(),
            "button_mask": m.button_mask.hex(),
            "imu_gravity_sector": m.imu_gravity_sector.hex(),
        },
    }
    outp = a.out_private if os.path.isabs(a.out_private) else os.path.join(_REPO, a.out_private)
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(priv, fh)
    print(f"  private inputs       : {a.out_private}")

    if not a.expect_public:
        return 0

    # ---- KILL-CHECK: recompute Poseidon root via the FROZEN helper, compare to committed ----
    res = subprocess.run(["node", _HELPER, outp, "--print-commitments"],
                         capture_output=True, text=True, timeout=300, cwd=_REPO)
    out = (res.stdout or "") + (res.stderr or "")
    if res.returncode != 0:
        print(f"  KILL-CHECK: INCOMPLETE — helper exit {res.returncode}: {out[-400:]}  (exit 2)")
        return 2
    root = None
    for line in out.splitlines():                     # helper prints sanitizedTraceRoot=<dec>
        if "sanitizedTraceRoot" in line:
            root = line.split("=")[-1].strip().strip('",')
    if root is None:
        try:                                          # or JSON with the field
            root = str(json.loads(out).get("sanitizedTraceRoot"))
        except Exception:  # noqa: BLE001
            pass
    if root is None:
        print(f"  KILL-CHECK: INCOMPLETE — could not parse root from helper output  (exit 2)\n{out[-400:]}")
        return 2
    expected = str(json.load(open(a.expect_public, encoding="utf-8"))[1])
    print(f"  recomputed root      : {root}")
    print(f"  committed  root      : {expected}  (public[1])")
    if root == expected:
        print("  KILL-CHECK: PASS — matrix regeneration is DETERMINISTIC vs the real proof  (exit 0)")
        return 0
    print("  KILL-CHECK: FAIL — phi non-determinism or DB drift; STOP the promote  (exit 1)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
