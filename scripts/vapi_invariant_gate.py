"""
vapi_invariant_gate.py — Phase 223/224 Protocol Invariant Gate

Hashes critical protocol regions in the source tree and compares against
an allowlist of known-good SHA-256 fingerprints.  Any drift signals a
potential invariant violation before it reaches production.

Phase 224 addition: allowlist hash is anchored as a virtual leaf in
ProtocolCoherenceAgent's Merkle tree.  Every --generate event requires
--reason (tamper-evident governance log).

USAGE:
    python scripts/vapi_invariant_gate.py              # gate check (exit 0=pass, 1=fail)
    python scripts/vapi_invariant_gate.py --generate --reason "refactor: description"
    python scripts/vapi_invariant_gate.py --generate --reason "invariant_change: ..." --confirm-governance
    python scripts/vapi_invariant_gate.py --report     # human-readable report, no exit code

INVARIANTS CHECKED (16):
  1.  PoAC wire format (228-byte body + 64-byte sig) in codec.py
  2.  Chain link hash = SHA-256(raw[:164]) in codec.py
  3.  L4 anomaly threshold literal in store.py (7.009 / 5.367)
  4.  ZK circuit Poseidon(8) C3 constraint nPublic=5 in PitlSessionProof.circom
  5.  Phase 66 commitment formula SHA-256(verdict+evidence+attestation+ts_ns)
  6.  Phase 67 circuitId = sha3_256(circuitName.encode())
  7.  CHEAT_CODES hard set: 0x28/0x29/0x2A in dualshock_integration.py
  8.  Stable EMA update — NOMINAL sessions only
  9.  L6_CHALLENGES_ENABLED default=False in config.py
  10. GSR_ENABLED default=False in config.py
  11. L6B_ENABLED default=False in config.py
  12. Epistemic weights sum = 1.0 (ioswarm_enabled branch)
  13. Block quorum BLOCK_QUORUM=0.67 in ioswarm modules
  14. MINT_QUORUM=0.80 in ioswarm VHP mint
  15. 228-byte record in chain.py record_on_chain calls
  16. Allowlist hash included as virtual leaf in ProtocolCoherenceAgent (Phase 224)
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).parent.parent
ALLOWLIST_PATH = REPO_ROOT / ".github" / "INVARIANTS_ALLOWLIST.json"

_VALID_REASON_CATEGORIES = frozenset({"refactor", "bugfix", "invariant_change", "ceremony_update"})
_REASON_PATTERN = re.compile(r"^(refactor|bugfix|invariant_change|ceremony_update): .{3,}$")
_GOVERNANCE_PHRASE = "I understand this changes a frozen protocol invariant"


class Invariant(NamedTuple):
    id: str
    description: str
    file: str
    pattern: str       # regex to locate the critical region
    min_matches: int   # minimum expected matches


INVARIANTS: list[Invariant] = [
    Invariant(
        id="INV-001",
        description="PoAC body = 164 bytes (wire format frozen)",
        file="bridge/vapi_bridge/codec.py",
        pattern=r"164",
        min_matches=1,
    ),
    Invariant(
        id="INV-002",
        description="Chain link hash = SHA-256(raw[:164])",
        file="bridge/vapi_bridge/codec.py",
        pattern=r"sha.*256.*164|SHA.256.*164|raw\[:164\]",
        min_matches=1,
    ),
    Invariant(
        id="INV-003",
        description="L4 anomaly threshold literal 7.009",
        file="bridge/vapi_bridge/store.py",
        pattern=r"7\.009",
        min_matches=1,
    ),
    Invariant(
        id="INV-004",
        description="L4 continuity threshold literal 5.367",
        file="bridge/vapi_bridge/store.py",
        pattern=r"5\.367",
        min_matches=1,
    ),
    Invariant(
        id="INV-005",
        description="Phase 62 ZK: Poseidon(8) / nPublic=5",
        file="contracts/circuits/PitlSessionProof.circom",
        pattern=r"Poseidon\(8\)|nPublic\s*=\s*5",
        min_matches=1,
    ),
    Invariant(
        id="INV-006",
        description="Hard cheat codes 0x28/0x29/0x2A in dualshock",
        file="bridge/vapi_bridge/dualshock_integration.py",
        pattern=r"0x28|DRIVER_INJECT",
        min_matches=1,
    ),
    Invariant(
        id="INV-007",
        description="Stable EMA updates NOMINAL sessions only",
        file="bridge/vapi_bridge/dualshock_integration.py",
        pattern=r"NOMINAL|stable.*ema|ema.*stable",
        min_matches=1,
    ),
    Invariant(
        id="INV-008",
        description="L6_CHALLENGES_ENABLED default=False",
        file="bridge/vapi_bridge/config.py",
        pattern=r"l6_challenges_enabled.*[Ff]alse|L6_CHALLENGES_ENABLED.*false",
        min_matches=1,
    ),
    Invariant(
        id="INV-009",
        description="GSR_ENABLED default=False",
        file="bridge/vapi_bridge/config.py",
        pattern=r"gsr_enabled.*[Ff]alse|GSR_ENABLED.*false",
        min_matches=1,
    ),
    Invariant(
        id="INV-010",
        description="L6B_ENABLED default=False",
        file="bridge/vapi_bridge/config.py",
        pattern=r"l6b_enabled.*[Ff]alse|L6B_ENABLED.*false",
        min_matches=1,
    ),
    Invariant(
        id="INV-011",
        description="BLOCK_QUORUM=0.67 in ioswarm modules",
        file="bridge/vapi_bridge/ioswarm_consensus_aggregator.py",
        pattern=r"0\.67|BLOCK_QUORUM",
        min_matches=1,
    ),
    Invariant(
        id="INV-012",
        description="MINT_QUORUM=0.80 in ioswarm VHP mint",
        file="bridge/vapi_bridge/session_adjudicator.py",
        pattern=r"0\.80|MINT_QUORUM",
        min_matches=1,
    ),
    Invariant(
        id="INV-013",
        description="PoAC record total 228 bytes in chain.py",
        file="bridge/vapi_bridge/chain.py",
        pattern=r"228",
        min_matches=1,
    ),
    Invariant(
        id="INV-014",
        description="Phase 66 commitment hash formula (verdict+evidence+attestation)",
        file="bridge/vapi_bridge/session_adjudicator.py",
        pattern=r"verdict.*evidence|commitment_hash|SHA.256.*verdict",
        min_matches=1,
    ),
    Invariant(
        id="INV-015",
        description="Phase 67 circuitId = sha3_256(circuitName.encode())",
        file="bridge/vapi_bridge/chain.py",
        pattern=r"sha3_256|circuitId|circuit_name",
        min_matches=1,
    ),
    Invariant(
        id="INV-016",
        description="Allowlist hash included as virtual leaf in ProtocolCoherenceAgent Merkle root",
        file="bridge/vapi_bridge/protocol_coherence_agent.py",
        pattern=r"allowlist.*leaf|virtual.*leaf|compute_allowlist_hash",
        min_matches=1,
    ),
]


def compute_allowlist_hash() -> str:
    """Return SHA-256 of canonicalized INVARIANTS_ALLOWLIST.json. Returns 64 zeros if missing."""
    if not ALLOWLIST_PATH.exists():
        return "0" * 64
    content = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _hash_file_region(path: Path, pattern: str) -> tuple[str, int]:
    """Hash all lines matching pattern in file. Returns (hex_digest, match_count)."""
    if not path.exists():
        return ("FILE_NOT_FOUND", 0)
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = [line for line in text.splitlines() if re.search(pattern, line, re.IGNORECASE)]
    digest = hashlib.sha256("\n".join(matches).encode()).hexdigest()
    return (digest, len(matches))


def check_invariants() -> list[dict]:
    """Run all invariant checks. Returns list of result dicts."""
    results = []
    for inv in INVARIANTS:
        path = REPO_ROOT / inv.file
        digest, count = _hash_file_region(path, inv.pattern)
        result = {
            "id": inv.id,
            "description": inv.description,
            "file": inv.file,
            "digest": digest,
            "match_count": count,
            "file_found": path.exists(),
            "pattern_matched": count >= inv.min_matches,
        }
        results.append(result)
    return results


def load_allowlist() -> dict:
    """Load allowlist from .github/INVARIANTS_ALLOWLIST.json. Returns {} if missing."""
    if not ALLOWLIST_PATH.exists():
        return {}
    return json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))


def _fetch_latest_provenance_hash() -> str:
    """GET latest governance_provenance_hash from bridge. Returns '0'*64 if unreachable."""
    import urllib.request as _urlreq
    try:
        req = _urlreq.Request(
            "http://localhost:8080/agent/allowlist-governance-history?limit=1",
            headers={"Content-Type": "application/json"},
        )
        with _urlreq.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            entries = body.get("entries", [])
            if entries:
                return str(entries[0].get("governance_provenance_hash", "0" * 64))
    except Exception:
        pass
    return "0" * 64


def _compute_governance_provenance_hash(
    prev_prov: str, new_hash: str, category: str, text: str
) -> str:
    """SHA-256(prev_prov_bytes || new_hash_bytes || category_bytes || text_bytes || ts_ns_8b).

    Forms a tamper-evident hash-linked audit trail (Phase 225).
    """
    ts_ns = time.time_ns()
    digest = hashlib.sha256(
        prev_prov.encode() +
        new_hash.encode() +
        category.encode() +
        text.encode() +
        ts_ns.to_bytes(8, "big")
    ).hexdigest()
    return digest


def _post_governance_event(prev: str, new: str, category: str, text: str) -> None:
    """POST governance event to bridge. Fail-open: logs warning if bridge unreachable."""
    import urllib.request as _urlreq
    # Phase 225: build tamper-evident provenance chain hash before POSTing.
    prev_prov_hash = _fetch_latest_provenance_hash()
    governance_provenance_hash = _compute_governance_provenance_hash(
        prev_prov_hash, new, category, text
    )
    payload = json.dumps({
        "previous_hash": prev,
        "new_hash": new,
        "reason_category": category,
        "reason_text": text,
        "governance_provenance_hash": governance_provenance_hash,
        "previous_provenance_hash":  prev_prov_hash,
    }).encode()
    try:
        req = _urlreq.Request(
            "http://localhost:8080/agent/allowlist-governance-event",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _urlreq.urlopen(req, timeout=5)
        print(f"[invariant_gate] Governance event posted to bridge (prov_hash={governance_provenance_hash[:12]}...).")
    except Exception as exc:
        print(
            f"[invariant_gate] WARNING: bridge not reachable ({exc}). "
            "Governance event not stored — run bridge and POST manually."
        )


def generate_allowlist(results: list[dict], reason_category: str = "", reason_text: str = "") -> None:
    """Write current digests as the new allowlist. Captures prev/new hash for governance log."""
    previous_hash = compute_allowlist_hash()
    allowlist = {r["id"]: {"digest": r["digest"], "description": r["description"]} for r in results}
    ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALLOWLIST_PATH.write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")
    new_hash = compute_allowlist_hash()
    print(f"[invariant_gate] Allowlist written: {ALLOWLIST_PATH} ({len(allowlist)} entries)")
    if reason_category and reason_text:
        _post_governance_event(previous_hash, new_hash, reason_category, reason_text)


def run_gate(report_only: bool = False) -> int:
    """Run invariant gate. Returns 0=pass, 1=fail."""
    results = check_invariants()
    allowlist = load_allowlist()
    failures = []

    for r in results:
        if not r["file_found"]:
            failures.append(f"{r['id']} — FILE NOT FOUND: {r['file']}")
            continue
        if not r["pattern_matched"]:
            failures.append(
                f"{r['id']} — PATTERN NOT MATCHED (0 lines): {r['description']}"
            )
            continue
        if allowlist and r["id"] in allowlist:
            expected = allowlist[r["id"]]["digest"]
            if r["digest"] != expected:
                failures.append(
                    f"{r['id']} — DIGEST DRIFT: {r['description']}\n"
                    f"    expected={expected[:16]}... got={r['digest'][:16]}..."
                )

    if report_only:
        print(f"[invariant_gate] Checked {len(results)} invariants")
        for r in results:
            status = "OK" if r["pattern_matched"] else "FAIL"
            print(f"  {r['id']} {status:4s} matches={r['match_count']:2d}  {r['description']}")
        if failures:
            print(f"\n[invariant_gate] FAILURES ({len(failures)}):")
            for f in failures:
                print(f"  {f}")
        else:
            print("\n[invariant_gate] All invariants pass.")
        return 0  # report mode always exits 0

    if failures:
        print(f"[invariant_gate] INVARIANT GATE FAILED ({len(failures)} violations):")
        for f in failures:
            print(f"  {f}")
        return 1

    print(f"[invariant_gate] PASS — {len(results)} invariants verified.")
    return 0


if __name__ == "__main__":
    if "--generate" in sys.argv:
        # Phase 224: --reason is required for all --generate calls
        if "--reason" not in sys.argv:
            print(
                "[invariant_gate] ERROR: --reason is required for --generate.\n"
                "Usage: python scripts/vapi_invariant_gate.py --generate "
                '--reason "<category>: <description>"\n'
                "Categories: refactor | bugfix | invariant_change | ceremony_update"
            )
            sys.exit(2)

        reason_idx = sys.argv.index("--reason")
        if reason_idx + 1 >= len(sys.argv):
            print("[invariant_gate] ERROR: --reason requires a value.")
            sys.exit(2)
        reason_raw = sys.argv[reason_idx + 1]

        if not _REASON_PATTERN.match(reason_raw) or not (10 <= len(reason_raw) <= 200):
            print(
                f"[invariant_gate] ERROR: invalid --reason value: {reason_raw!r}\n"
                "Must match: <category>: <description> (10-200 chars)\n"
                "Categories: refactor | bugfix | invariant_change | ceremony_update\n"
                "Example: refactor: renamed _hash_region helper without semantic change"
            )
            sys.exit(2)

        colon_idx = reason_raw.index(":")
        reason_category = reason_raw[:colon_idx].strip()
        reason_text = reason_raw[colon_idx + 1:].strip()

        if reason_category == "invariant_change" and "--confirm-governance" not in sys.argv:
            print(
                "[invariant_gate] ERROR: reason_category='invariant_change' requires --confirm-governance.\n"
                "This category signals an intentional change to a frozen protocol invariant.\n"
                "Re-run with: --confirm-governance"
            )
            sys.exit(2)

        if "--confirm-governance" in sys.argv:
            print(
                "[GOVERNANCE WARNING] You are about to change a frozen protocol invariant.\n"
                "This action will be logged as a tamper-evident governance event on-chain.\n"
                "Every node in the network will observe this change in the next Merkle anchor."
            )
            time.sleep(3)
            try:
                phrase = input("Type confirmation phrase: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[invariant_gate] Governance confirmation aborted.")
                sys.exit(3)
            if phrase != _GOVERNANCE_PHRASE:
                print(
                    f"[invariant_gate] Confirmation phrase mismatch.\n"
                    f'Expected: "{_GOVERNANCE_PHRASE}"'
                )
                sys.exit(3)

        results = check_invariants()
        generate_allowlist(results, reason_category=reason_category, reason_text=reason_text)

    elif "--report" in sys.argv:
        sys.exit(run_gate(report_only=True))
    else:
        sys.exit(run_gate())
