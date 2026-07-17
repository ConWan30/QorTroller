"""Replay an allowlist governance event that was missed while the bridge was offline.

WHY THIS EXISTS (A2A round-30 T4, option b + c): `vapi_invariant_gate.py --generate`
posts a governance event to the bridge AFTER writing the allowlist. When the bridge is
down at seal time it prints "Governance event not stored — run bridge and POST manually"
and the tamper-evident provenance chain in the bridge DB is missing that seal. The
INV-MFG-003 seal (commit `816b4d81`, PV-CI 183->184) is exactly such a gap.

HONESTY (LOAD-BEARING): this creates a **NEW** provenance-chain entry that DOCUMENTS an
offline seal — it does NOT and cannot backdate the original event. The governance
provenance hash is `SHA-256(prev_prov || new_hash || category || text || ts_ns)` with a
FRESH `ts_ns` at POST time (the gate's own formula, reused here, not reinvented), so a
late record is a new link that references the same allowlist transition. Write the reason
text so the record reads as a late record, e.g. "late record of INV-MFG-003 seal
(816b4d81)".

It never rewrites the allowlist and never re-runs the gate. Default is DRY-RUN (prints the
exact payload + the would-POST URL, no network write); `--execute` POSTs to the bridge.

Reusable for every future offline `--generate`. Examples:

  # dry-run: show the payload for the INV-MFG-003 offline seal (183 -> 184)
  python scripts/replay_governance_event.py \
      --prev-git-ref 74c864c8 --category invariant_change \
      --reason "late record of INV-MFG-003 seal (816b4d81), PV-CI 183->184"

  # POST it (bridge must be up; read key via OPERATOR_API_KEY / --api-key)
  python scripts/replay_governance_event.py \
      --prev-git-ref 74c864c8 --category invariant_change \
      --reason "late record of INV-MFG-003 seal (816b4d81), PV-CI 183->184" --execute
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Reuse the gate's canonicalization + provenance formula + URL — single source of truth.
from scripts.vapi_invariant_gate import (  # noqa: E402
    ALLOWLIST_PATH,
    _bridge_operator_url,
    _compute_governance_provenance_hash,
    _fetch_latest_provenance_hash,
    compute_allowlist_hash,
)

_ALLOWLIST_REL = ".github/INVARIANTS_ALLOWLIST.json"
_VALID_CATS = {"refactor", "bugfix", "invariant_change", "ceremony_update"}
_ZERO_PROV = "0" * 64


def _fetch_provenance_tip(api_key: str) -> str:
    """GET the current provenance-chain tip WITH x-api-key (grok r35 F1).

    The gate's `_fetch_latest_provenance_hash()` omits the key, so on a key-configured
    bridge with a NON-EMPTY chain it fails open to zeros — and a `--execute` POST with a
    zeros `previous_provenance_hash` would look like a SECOND genesis / chain break. Sending
    the read key gets the real tip. Falls back to the gate helper only when no key is set;
    any failure returns zeros (honest: caller warns before an --execute that would genesis).
    """
    if not api_key:
        return _fetch_latest_provenance_hash()
    try:
        req = urllib.request.Request(
            _bridge_operator_url("/agent/allowlist-governance-history?limit=1"),
            headers={"Content-Type": "application/json", "x-api-key": api_key},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            entries = json.loads(resp.read().decode()).get("entries", [])
            if entries:
                return str(entries[0].get("governance_provenance_hash", _ZERO_PROV))
    except Exception:  # noqa: BLE001 — unreachable/unauth -> zeros; caller guards --execute
        pass
    return _ZERO_PROV


def _hash_allowlist_content(text: str) -> str:
    """compute_allowlist_hash() for arbitrary allowlist JSON text (e.g. a git blob).
    Byte-identical canonicalization to the gate: sort_keys + compact separators."""
    content = json.loads(text)
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _allowlist_hash_at_ref(ref: str) -> str:
    """SHA-256 of the canonicalized allowlist as it was at a git ref (fail-loud)."""
    try:
        blob = subprocess.run(
            ["git", "show", f"{ref}:{_ALLOWLIST_REL}"],
            cwd=str(ROOT), capture_output=True, text=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"ERROR: could not read {_ALLOWLIST_REL} at git ref {ref!r}: "
            f"{(exc.stderr or '').strip()}"
        )
    return _hash_allowlist_content(blob)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prev-git-ref", help="git ref whose allowlist is the 'before' state "
                                          "(e.g. the seal commit's parent).")
    g.add_argument("--prev-hash", help="explicit before-hash (64 hex).")
    ap.add_argument("--new-hash", default=None,
                    help="after-hash (64 hex). Default: the CURRENT allowlist hash.")
    ap.add_argument("--category", required=True, choices=sorted(_VALID_CATS))
    ap.add_argument("--reason", required=True,
                    help="reason text, 10-200 chars. Write it as a LATE RECORD.")
    ap.add_argument("--api-key", default=os.environ.get("OPERATOR_API_KEY", ""),
                    help="operator read key (x-api-key). Default env OPERATOR_API_KEY.")
    ap.add_argument("--execute", action="store_true",
                    help="POST to the bridge. Default is dry-run (print payload only).")
    args = ap.parse_args()

    if not (10 <= len(args.reason) <= 200):
        raise SystemExit(f"ERROR: --reason must be 10-200 chars (got {len(args.reason)}).")

    prev_hash = args.prev_hash or _allowlist_hash_at_ref(args.prev_git_ref)
    new_hash = args.new_hash or compute_allowlist_hash()
    if prev_hash == new_hash:
        print("WARNING: prev-hash == new-hash — the allowlist did not change between these "
              "states. Recording this event would document a no-op transition.", file=sys.stderr)

    # Fetch the current provenance-chain tip (a NEW link chains onto it). Keyed fetch so an
    # auth'd non-empty chain returns the real tip, not zeros (grok r35 F1). Bridge-down/
    # unauth -> zeros, and --execute warns before recording a would-be genesis link.
    prev_prov_hash = _fetch_provenance_tip(args.api_key)
    gov_prov_hash = _compute_governance_provenance_hash(
        prev_prov_hash, new_hash, args.category, args.reason,
    )  # uses a FRESH ts_ns — this is a NEW record, not a backdated original.
    payload = {
        "previous_hash": prev_hash,
        "new_hash": new_hash,
        "reason_category": args.category,
        "reason_text": args.reason,
        "governance_provenance_hash": gov_prov_hash,
        "previous_provenance_hash": prev_prov_hash,
    }
    url = _bridge_operator_url("/agent/allowlist-governance-event")

    print("--- REPLAY GOVERNANCE EVENT (a NEW late record — does NOT backdate the original) ---")
    print(f"  before (prev_hash): {prev_hash}"
          + (f"  [git {args.prev_git_ref}]" if args.prev_git_ref else "  [explicit]"))
    print(f"  after  (new_hash) : {new_hash}"
          + ("  [current allowlist]" if not args.new_hash else "  [explicit]"))
    print(f"  provenance tip    : {prev_prov_hash[:16]}...  "
          + ("(bridge unreachable — zeros)" if prev_prov_hash == "0" * 64 else "(fetched live)"))
    print(f"  new prov hash     : {gov_prov_hash}")
    print(f"  POST url          : {url}")
    print("  payload           :")
    print(json.dumps(payload, indent=2))

    if not args.execute:
        print("\n[DRY-RUN] no POST. Re-run with --execute (bridge up + read key) to record it.")
        return

    # grok r35 F1 guard: a zeros tip means either the chain is genuinely empty (fine — a
    # legitimate first link, e.g. the INV-MFG-003 gap) OR the tip-fetch failed (bridge down /
    # no read key). Recording a zeros-prev link onto a NON-empty chain looks like a second
    # genesis. Surface it before posting; the operator confirms the chain is actually empty.
    if prev_prov_hash == _ZERO_PROV:
        print("\n[WARNING] provenance tip is all-zeros. This POST records a FIRST/genesis link. "
              "That is correct ONLY if the chain is genuinely empty. If the bridge has a "
              "provenance chain already, ensure the read key is set (x-api-key) so the tip is "
              "fetched — otherwise you would append a false second genesis.")

    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["x-api-key"] = args.api_key
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"\n[POSTED] HTTP {resp.status}: {resp.read().decode()[:400]}")
    except Exception as exc:  # noqa: BLE001 — surface honestly, no fabrication
        raise SystemExit(
            f"\nERROR: POST failed ({exc}). Is the bridge up on the operator port and is the "
            f"read key correct (x-api-key)? The allowlist is unchanged either way — this tool "
            f"only records the provenance event."
        )


if __name__ == "__main__":
    main()
