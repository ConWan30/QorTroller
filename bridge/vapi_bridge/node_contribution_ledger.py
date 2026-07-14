"""DEPIN-1 LEG 3 (NODE-LEDGER-1) — hash-chained node contribution ledger.

Candidate domain tag (PoSP-style REFERENCE-AND-BIND — NOT a new FROZEN-v1 family):

  GENESIS(node_id) = SHA-256(
      b"QORTROLLER-NODE-LEDGER-GENESIS-v0" || node_id_32b
  )

  entry_hash = SHA-256(
      b"QORTROLLER-NODE-LEDGER-v0"
      || prev32                 # 32B: genesis or prior entry_hash for this node_id
      || node_id_32b            # 32B
      || utf8(session_id)       # variable
      || scorecard_root_32b     # 32B
      || posp_verdict_code      # 1B
      || w3s_attested           # 1B (0x00 | 0x01)
      || ts_ns_be               # 8B big-endian uint64
  )

Honesty rails
-------------
* Ledger is LOCAL and tamper-evident until anchored.
* ``anchored`` / ``anchor_tx`` / ``anchor_block`` are NOT in the hash preimage so a
  real post-confirmation update does not break the chain; they stay false/null until
  a real IoTeX tx confirms (never fabricate).
* ``w3s_attested`` means leg-2 mechanical format/presence only — NOT network truth.
* No PoAC / FROZEN-v1 / secrets surface. Anchor spend is operator-fired elsewhere.
"""
from __future__ import annotations

import hashlib
import json
import struct
import time
from pathlib import Path
from typing import Any, Iterable

# --------------------------------------------------------------------------- domain tags (candidate)
LEDGER_DOMAIN_TAG = b"QORTROLLER-NODE-LEDGER-v0"
LEDGER_DOMAIN = "QORTROLLER-NODE-LEDGER-v0"
LEDGER_GENESIS_TAG = b"QORTROLLER-NODE-LEDGER-GENESIS-v0"
LEDGER_ENTRY_SCHEMA = "qortroller-node-ledger-entry-v0"
SCORECARD_ROOT_TAG = b"QORTROLLER-SCORECARD-ROOT-v0"
DEFAULT_LEDGER_NAME = "node_contribution_ledger.jsonl"

# PoSP verdict → 1-byte code (ABSENT covers missing / unknown)
POSP_VERDICT_CODES: dict[str, int] = {
    "ABSENT": 0x00,
    "UNVERIFIABLE": 0x01,
    "PARTIAL_SURFACES": 0x02,
    "SYNCHRONIZED": 0x03,
}
POSP_VERDICT_NAMES: dict[int, str] = {v: k for k, v in POSP_VERDICT_CODES.items()}

ANCHOR_STATE_PENDING = "PENDING"
ANCHOR_STATE_ANCHORED = "ANCHORED"

W3S_ATTESTED_MEANING = (
    "sandbox verified format/presence of node_id+session_root (leg-2 mechanical gate) "
    "— NOT network-validated truth, NOT re-derived node_id, NOT recomputed session_root"
)

LEDGER_MAY_CLAIM = (
    "entry_hash is a LOCAL hash-chain link recomputable from public fields",
    "chain_intact means consecutive entry_hash values match recomputed preimages",
    "anchored=true only after a real IoTeX tx confirms (operator-fired)",
    "w3s_attested reflects leg-2 mechanical format/presence when true",
)

LEDGER_MUST_NOT_CLAIM = (
    "contribution is on-chain while anchored=false / PENDING",
    "fabricated tx hash or block without a confirmed receipt",
    "w3s_attested means decentralized-verified identity truth",
    "node_id is minted / registered as on-chain identity",
    "new FROZEN-v1 commitment family",
    "autonomous spend (anchor is operator-fired + triple-gated)",
)


# --------------------------------------------------------------------------- pure crypto


def _norm_hex32(value: str, *, label: str) -> str:
    if value is None:
        raise ValueError(f"{label} is required")
    h = str(value).strip().lower().removeprefix("0x")
    if len(h) != 64:
        raise ValueError(f"{label} must be 32 bytes (64 hex), got len={len(h)}")
    try:
        bytes.fromhex(h)
    except ValueError as exc:
        raise ValueError(f"{label} is not valid hex: {exc}") from exc
    return h


def posp_verdict_code(verdict: str | None) -> int:
    """Map a PoSP verdict string to the 1-byte ledger code (unknown → ABSENT)."""
    if not verdict:
        return POSP_VERDICT_CODES["ABSENT"]
    key = str(verdict).strip().upper()
    return POSP_VERDICT_CODES.get(key, POSP_VERDICT_CODES["ABSENT"])


def genesis_hash(node_id_hex: str) -> bytes:
    """Per-node_id genesis prev link (deterministic; no timestamp)."""
    nid = _norm_hex32(node_id_hex, label="node_id")
    return hashlib.sha256(LEDGER_GENESIS_TAG + bytes.fromhex(nid)).digest()


def genesis_hash_hex(node_id_hex: str) -> str:
    return genesis_hash(node_id_hex).hex()


def compute_scorecard_root(scorecard: dict | bytes | str | Path) -> str:
    """32-byte scorecard commitment (hex).

    * bytes / Path / str path → SHA-256 over exact file/raw bytes (PoSP-file-digest style).
    * dict → SHA-256(b"QORTROLLER-SCORECARD-ROOT-v0" || canonical JSON utf-8).
    """
    if isinstance(scorecard, (bytes, bytearray)):
        return hashlib.sha256(bytes(scorecard)).hexdigest()
    if isinstance(scorecard, Path) or (
        isinstance(scorecard, str) and ("\n" not in scorecard) and Path(scorecard).is_file()
    ):
        raw = Path(scorecard).read_bytes()
        return hashlib.sha256(raw).hexdigest()
    if isinstance(scorecard, dict):
        body = json.dumps(
            scorecard, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(SCORECARD_ROOT_TAG + body).hexdigest()
    if isinstance(scorecard, str):
        # treat as raw UTF-8 payload (tests / explicit strings that are not paths)
        return hashlib.sha256(scorecard.encode("utf-8")).hexdigest()
    raise TypeError(f"unsupported scorecard type: {type(scorecard)!r}")


def compute_entry_hash(
    *,
    prev_hash: bytes | str,
    node_id_hex: str,
    session_id: str,
    scorecard_root_hex: str,
    posp_verdict: str | None,
    w3s_attested: bool,
    ts_ns: int,
) -> bytes:
    """Compute one ledger link hash. Pure — no I/O."""
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id must be a non-empty str")
    if not isinstance(ts_ns, int) or ts_ns < 0:
        raise ValueError("ts_ns must be a non-negative int")
    if isinstance(prev_hash, str):
        prev = bytes.fromhex(_norm_hex32(prev_hash, label="prev_hash"))
    else:
        if not isinstance(prev_hash, (bytes, bytearray)) or len(prev_hash) != 32:
            raise ValueError("prev_hash must be 32 bytes")
        prev = bytes(prev_hash)
    nid = _norm_hex32(node_id_hex, label="node_id")
    root = _norm_hex32(scorecard_root_hex, label="scorecard_root")
    code = posp_verdict_code(posp_verdict)
    attested_b = b"\x01" if w3s_attested else b"\x00"
    preimage = (
        LEDGER_DOMAIN_TAG
        + prev
        + bytes.fromhex(nid)
        + session_id.encode("utf-8")
        + bytes.fromhex(root)
        + code.to_bytes(1, "big")
        + attested_b
        + struct.pack(">Q", ts_ns)
    )
    return hashlib.sha256(preimage).digest()


def compute_entry_hash_hex(**kwargs: Any) -> str:
    return compute_entry_hash(**kwargs).hex()


def build_entry(
    *,
    node_id_hex: str,
    session_id: str,
    scorecard_root_hex: str,
    posp_verdict: str | None = None,
    w3s_attested: bool = False,
    ts_ns: int | None = None,
    prev_hash_hex: str | None = None,
) -> dict[str, Any]:
    """Build one ledger entry dict (PENDING anchor). Hash-covered fields frozen at creation."""
    nid = _norm_hex32(node_id_hex, label="node_id")
    root = _norm_hex32(scorecard_root_hex, label="scorecard_root")
    ts = int(ts_ns if ts_ns is not None else time.time_ns())
    if prev_hash_hex is None:
        prev = genesis_hash(nid)
        prev_hex = prev.hex()
    else:
        prev_hex = _norm_hex32(prev_hash_hex, label="prev_hash")
        prev = bytes.fromhex(prev_hex)
    code = posp_verdict_code(posp_verdict)
    verdict_name = POSP_VERDICT_NAMES.get(code, "ABSENT")
    eh = compute_entry_hash(
        prev_hash=prev,
        node_id_hex=nid,
        session_id=session_id,
        scorecard_root_hex=root,
        posp_verdict=verdict_name,
        w3s_attested=bool(w3s_attested),
        ts_ns=ts,
    )
    return {
        "schema": LEDGER_ENTRY_SCHEMA,
        "domain": LEDGER_DOMAIN,
        "node_id": nid,
        "session_id": session_id,
        "scorecard_root": root,
        "posp_verdict": verdict_name,
        "posp_verdict_code": code,
        "w3s_attested": bool(w3s_attested),
        "w3s_attested_meaning": W3S_ATTESTED_MEANING,
        "ts_ns": ts,
        "prev_hash": prev_hex,
        "entry_hash": eh.hex(),
        # mutable, NOT in preimage — stay false/null until real tx confirms
        "anchored": False,
        "anchor_state": ANCHOR_STATE_PENDING,
        "anchor_tx": None,
        "anchor_block": None,
        "may_claim": list(LEDGER_MAY_CLAIM),
        "must_not_claim": list(LEDGER_MUST_NOT_CLAIM),
    }


# --------------------------------------------------------------------------- chain verify


def verify_entry(entry: dict) -> tuple[bool, str]:
    """Recompute entry_hash from stored fields. Returns (ok, reason)."""
    try:
        expected = compute_entry_hash_hex(
            prev_hash=entry["prev_hash"],
            node_id_hex=entry["node_id"],
            session_id=entry["session_id"],
            scorecard_root_hex=entry["scorecard_root"],
            posp_verdict=entry.get("posp_verdict"),
            w3s_attested=bool(entry.get("w3s_attested")),
            ts_ns=int(entry["ts_ns"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"malformed entry: {exc}"
    claimed = str(entry.get("entry_hash") or "").strip().lower().removeprefix("0x")
    if claimed != expected:
        return False, "entry_hash mismatch (tamper or wrong fields)"
    return True, "ok"


def verify_chain(entries: Iterable[dict], *, node_id_hex: str | None = None) -> dict[str, Any]:
    """Verify per-node hash chain. Surfaces breaks like GIC chain_intact=False.

    Returns:
      chain_intact, entry_count, breaks[{index,session_id,reason}], nodes_checked
    """
    rows = list(entries)
    if node_id_hex:
        nid_filter = _norm_hex32(node_id_hex, label="node_id")
        rows = [r for r in rows if str(r.get("node_id", "")).lower().removeprefix("0x") == nid_filter]

    # group by node_id in file order
    by_node: dict[str, list[tuple[int, dict]]] = {}
    for i, e in enumerate(rows):
        try:
            nid = _norm_hex32(str(e.get("node_id", "")), label="node_id")
        except ValueError:
            by_node.setdefault("__malformed__", []).append((i, e))
            continue
        by_node.setdefault(nid, []).append((i, e))

    breaks: list[dict[str, Any]] = []
    for nid, pairs in by_node.items():
        if nid == "__malformed__":
            for i, e in pairs:
                breaks.append({
                    "index": i,
                    "session_id": e.get("session_id"),
                    "reason": "malformed node_id",
                })
            continue
        expected_prev = genesis_hash_hex(nid)
        for i, e in pairs:
            ok, reason = verify_entry(e)
            if not ok:
                breaks.append({
                    "index": i,
                    "session_id": e.get("session_id"),
                    "node_id": nid,
                    "reason": reason,
                })
                # still advance using claimed hash so subsequent break reasons stay local
            prev_claimed = str(e.get("prev_hash") or "").strip().lower().removeprefix("0x")
            if prev_claimed != expected_prev:
                breaks.append({
                    "index": i,
                    "session_id": e.get("session_id"),
                    "node_id": nid,
                    "reason": f"prev_hash break (expected {expected_prev[:16]}…, got {prev_claimed[:16]}…)",
                })
            eh = str(e.get("entry_hash") or "").strip().lower().removeprefix("0x")
            expected_prev = eh if len(eh) == 64 else expected_prev

    return {
        "chain_intact": len(breaks) == 0,
        "entry_count": len(rows),
        "breaks": breaks,
        "nodes_checked": sorted(k for k in by_node if k != "__malformed__"),
    }


# --------------------------------------------------------------------------- JSONL store


def default_ledger_path(home: Path | None = None) -> Path:
    base = home if home is not None else Path.home() / ".qortroller"
    return Path(base) / DEFAULT_LEDGER_NAME


def load_ledger(path: Path | str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            out.append({"_raw": line, "schema": "malformed"})
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def entries_for_node(entries: list[dict], node_id_hex: str) -> list[dict]:
    nid = _norm_hex32(node_id_hex, label="node_id")
    return [
        e for e in entries
        if str(e.get("node_id", "")).lower().removeprefix("0x") == nid
    ]


def latest_entry_hash(entries: list[dict], node_id_hex: str) -> str | None:
    """Return the tip entry_hash for node_id, or None if no entries (caller uses genesis)."""
    rows = entries_for_node(entries, node_id_hex)
    if not rows:
        return None
    return str(rows[-1].get("entry_hash") or "") or None


def find_entry_by_session(
    entries: list[dict],
    session_id: str,
    *,
    node_id_hex: str | None = None,
) -> dict | None:
    sid = str(session_id)
    for e in reversed(entries):
        if e.get("session_id") != sid:
            continue
        if node_id_hex:
            try:
                if _norm_hex32(str(e.get("node_id", "")), label="node_id") != _norm_hex32(
                    node_id_hex, label="node_id"
                ):
                    continue
            except ValueError:
                continue
        return e
    return None


def append_entry(path: Path | str, entry: dict) -> dict:
    """Append one entry to JSONL. Raises ValueError if session already present for node."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = load_ledger(p)
    nid = _norm_hex32(str(entry["node_id"]), label="node_id")
    sid = entry["session_id"]
    if find_entry_by_session(existing, sid, node_id_hex=nid) is not None:
        raise ValueError(f"session_id already in ledger for this node_id: {sid!r}")
    # enforce prev_hash continuity if caller left it as genesis but tip exists
    tip = latest_entry_hash(existing, nid)
    if tip and entry.get("prev_hash") == genesis_hash_hex(nid):
        # rebuild with correct prev (honest fix rather than silent fork)
        entry = build_entry(
            node_id_hex=nid,
            session_id=sid,
            scorecard_root_hex=entry["scorecard_root"],
            posp_verdict=entry.get("posp_verdict"),
            w3s_attested=bool(entry.get("w3s_attested")),
            ts_ns=int(entry["ts_ns"]),
            prev_hash_hex=tip,
        )
    ok, reason = verify_entry(entry)
    if not ok:
        raise ValueError(f"refusing to append invalid entry: {reason}")
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
    return entry


def mark_anchored(
    path: Path | str,
    *,
    session_id: str,
    tx_hash: str,
    block_number: int | None,
    node_id_hex: str | None = None,
) -> dict:
    """Update non-hashed anchor fields after a real confirmed tx. Never invents tx.

    Rewrites the JSONL (only allowed mutation of mutable fields). Raises if entry missing
    or tx_hash empty.
    """
    tx = str(tx_hash or "").strip()
    if not tx:
        raise ValueError("tx_hash required — never fabricate an anchor")
    if not tx.startswith("0x"):
        tx = "0x" + tx
    p = Path(path)
    entries = load_ledger(p)
    target = find_entry_by_session(entries, session_id, node_id_hex=node_id_hex)
    if target is None:
        raise ValueError(f"no ledger entry for session_id={session_id!r}")
    # mutate the matching object in the list
    for e in entries:
        if e is target or (
            e.get("session_id") == session_id
            and e.get("entry_hash") == target.get("entry_hash")
        ):
            e["anchored"] = True
            e["anchor_state"] = ANCHOR_STATE_ANCHORED
            e["anchor_tx"] = tx
            e["anchor_block"] = block_number
            # re-verify hash fields unchanged
            ok, reason = verify_entry(e)
            if not ok:
                raise ValueError(f"anchor update broke entry_hash: {reason}")
            target = e
            break
    # rewrite full file (preserves order)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, sort_keys=True, separators=(",", ":")) + "\n")
    tmp.replace(p)
    return target


def render_ledger_report(
    entries: list[dict],
    *,
    node_id_hex: str | None = None,
    verify: bool = True,
) -> str:
    """ASCII report for CLI. Surfaces chain breaks; never claims on-chain when PENDING."""
    rows = entries_for_node(entries, node_id_hex) if node_id_hex else list(entries)
    v = verify_chain(rows, node_id_hex=node_id_hex) if verify else {
        "chain_intact": None, "entry_count": len(rows), "breaks": [], "nodes_checked": [],
    }
    L = [
        "=" * 64,
        "  QorTroller Node Contribution Ledger  (NODE-LEDGER-1)",
        "=" * 64,
        f"  Domain     : {LEDGER_DOMAIN}  (candidate — not FROZEN-v1)",
        f"  Entries    : {v['entry_count']}",
        f"  Chain      : {'INTACT' if v['chain_intact'] else ('BREAK' if v['chain_intact'] is False else 'SKIPPED')}",
    ]
    if node_id_hex:
        L.append(f"  Node       : {node_id_hex[:16]}…")
    L.append("-" * 64)
    if not rows:
        L.append("  (empty — append a scorecard contribution first)")
    for i, e in enumerate(rows):
        state = e.get("anchor_state") or (
            ANCHOR_STATE_ANCHORED if e.get("anchored") else ANCHOR_STATE_PENDING
        )
        # honesty: never print "on-chain" for PENDING
        if state == ANCHOR_STATE_ANCHORED and e.get("anchor_tx"):
            anchor_line = f"ANCHORED tx={(e.get('anchor_tx') or '')[:18]}…"
        else:
            anchor_line = "PENDING (local only — not on-chain)"
        w3s = "w3s=Y" if e.get("w3s_attested") else "w3s=N"
        L.append(
            f"  [{i:03d}] session={e.get('session_id')}  "
            f"posp={e.get('posp_verdict')}  {w3s}  {anchor_line}"
        )
        L.append(
            f"         entry_hash={str(e.get('entry_hash') or '')[:16]}…  "
            f"root={str(e.get('scorecard_root') or '')[:12]}…"
        )
    if v.get("breaks"):
        L.append("-" * 64)
        L.append("  BREAKS (tamper-evident):")
        for b in v["breaks"]:
            L.append(f"    idx={b.get('index')} session={b.get('session_id')} — {b.get('reason')}")
    L.append("-" * 64)
    L.append("  MUST NOT: claim on-chain while PENDING; over-read w3s_attested as truth.")
    L.append("  MAY: recompute entry_hash; operator-fire anchor estimate-first.")
    L.append("=" * 64)
    return "\n".join(L)


def extract_scorecard_fields(scorecard: dict) -> dict[str, Any]:
    """Pull node_id / session_id / posp_verdict from a VALID-1 scorecard dict."""
    node_cell = scorecard.get("node_id") or (scorecard.get("fields") or {}).get("node_id") or {}
    node_v = node_cell.get("value") if isinstance(node_cell, dict) else None
    node_id = None
    if isinstance(node_v, dict):
        node_id = node_v.get("node_id")
    elif isinstance(node_v, str):
        node_id = node_v
    bind = scorecard.get("session_bind") or {}
    session_id = bind.get("session_id") or scorecard.get("session_id")
    fields = scorecard.get("fields") or {}
    posp_cell = fields.get("posp_verdict") or {}
    posp = posp_cell.get("value") if isinstance(posp_cell, dict) else posp_cell
    return {
        "node_id": node_id,
        "session_id": session_id,
        "posp_verdict": posp,
        "label": scorecard.get("label"),
    }
