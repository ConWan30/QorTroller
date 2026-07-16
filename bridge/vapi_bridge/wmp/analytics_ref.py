"""WMP UC-5 — Provenance-preserving analytics: CANONICAL PYTHON REFERENCE (A2A round-1, grok-designed).

The product is a W3bstream/wasm applet that computes aggregate statistics over consented export rows so
a buyer verifies the STATISTIC (not the raw data). This module is the language-agnostic REFERENCE the
wasm port must reproduce byte-for-byte (the repo's established Python-mirror pattern, e.g.
`resolve_node_session`). It is fully testable here; the Rust `wasm32-unknown-unknown` port is deferred to
a toolchain-available env (the target is uninstallable in this sandbox) and validated in CI against these
same parity vectors — see `docs/wmp-uc5-wasm-analytics-design.md`.

HARD RAILS (grok round-1 highest-risk hammers, enforced fail-closed):
  - CONSENT binding (NOT a consent oracle): each row's consent_bits + cross_aggregate flag are bound INTO
    its provenance commitment, so a SILENT consent flip on a fixed preimage is defeated (the buyer
    re-hashes the same preimage and sees the same root). A host that ALSO fabricates the
    gamer_export_commitment remains format-not-truth — the applet attests format+aggregation, never that
    the published export is truthful (DEPIN-1 ceiling; stated in the `ceiling` field + design doc).
  - The requested export category's consent bit MUST be set on every row (fail-closed).
  - CROSS-GAMER aggregation (>1 distinct gamer_export_commitment) requires EVERY row's
    cross_aggregate_ok == True — no single global consent flag.
  - field_id MUST be in the FROZEN ALLOWLIST (non-biometric integer fields only). No IMU / tremor /
    humanity / liveness / APM-from-biometric. No float in the attested surface (mean is fixed-point).

Pure stdlib; deterministic.
"""
from __future__ import annotations

import hashlib

REF_VERSION = "wmp-analytics-ref-v0"
_ROW_DOMAIN = b"WMP-ANALYTICS-ROW-v0"

# FROZEN consent categories (mirror the CONSENT-v1 enum: position-for-position with VAPIConsentRegistry).
CONSENT_CATEGORIES = {"TOURNAMENT_GATE": 0, "ANONYMIZED_RESEARCH": 1, "MANUFACTURER_CERT": 2, "MARKETPLACE": 3}

# FROZEN allowlist — non-biometric integer fields only. Everything else is rejected (deny-by-default).
FIELD_ALLOWLIST = frozenset({"session_tick_count", "match_span_s", "authored_kill_count",
                             "clean_session_count", "verdict_class"})
OPS = ("count", "sum", "mean", "p50", "hist")


class ConsentError(ValueError):
    """Raised (fail-closed) when a row violates the consent / allowlist rails."""


def _u32(n: int) -> bytes:
    return int(n).to_bytes(4, "big")


def row_commitment(row: dict) -> str:
    """Provenance bind: SHA-256(DOMAIN | field_id | be64(value) | be32(consent_bits) | cross_u8 |
    gamer_export_commitment(32B)). The consent bits + cross flag are IN the preimage, so consent cannot
    be forged without the published gamer_export_commitment (grok round-1 rail)."""
    field_id = str(row["field_id"])
    value = int(row["value_i64"])
    consent_bits = int(row["consent_bits"])
    cross = 1 if row.get("cross_aggregate_ok") else 0
    gec = str(row["gamer_export_commitment"])
    if len(gec) != 64 or any(c not in "0123456789abcdefABCDEF" for c in gec):
        raise ConsentError(f"gamer_export_commitment must be 64-hex, got {gec!r}")
    body = (_ROW_DOMAIN + b"|" + field_id.encode() + b"|"
            + value.to_bytes(8, "big", signed=True) + _u32(consent_bits)
            + bytes([cross]) + bytes.fromhex(gec))
    return hashlib.sha256(body).hexdigest()


def _merkle_root(leaves_hex: list[str]) -> str:
    """sha256-sorted-leaf-merkle-v0: sort leaf digests, pairwise-hash up (dup last if odd)."""
    if not leaves_hex:
        return hashlib.sha256(b"WMP-ANALYTICS-EMPTY-v0").hexdigest()
    level = sorted(leaves_hex)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest())
        level = nxt
    return level[0]


def gate_rows(rows: list[dict], *, requested_category: str) -> list[dict]:
    """Fail-closed consent + allowlist gate. Returns the accepted rows or raises ConsentError."""
    if requested_category not in CONSENT_CATEGORIES:
        raise ConsentError(f"unknown export category {requested_category!r}")
    bit = 1 << CONSENT_CATEGORIES[requested_category]
    gamers: set[str] = set()
    for r in rows:
        if str(r.get("field_id")) not in FIELD_ALLOWLIST:
            raise ConsentError(f"field_id {r.get('field_id')!r} not in FROZEN allowlist (deny-by-default)")
        if (int(r.get("consent_bits", 0)) & bit) == 0:
            raise ConsentError(f"row lacks consent for {requested_category} (bit {bit} unset)")
        gamers.add(str(r["gamer_export_commitment"]))
    if len(gamers) > 1 and not all(r.get("cross_aggregate_ok") for r in rows):
        raise ConsentError("cross-gamer aggregation requires cross_aggregate_ok=True on EVERY row")
    return list(rows)


def aggregate(rows: list[dict], *, op: str, field_id: str, requested_category: str,
              applet_semver: str = REF_VERSION, wasm_sha256: str = "") -> dict:
    """Compute one consent-gated aggregate over `field_id` rows -> the (statistic, commitment-set,
    version) triple. Fail-closed: gate first, reject unknown op/field, integer/fixed-point only."""
    if op not in OPS:
        raise ConsentError(f"unknown op {op!r}")
    if field_id not in FIELD_ALLOWLIST:
        raise ConsentError(f"field_id {field_id!r} not in FROZEN allowlist")
    sel = [r for r in rows if str(r.get("field_id")) == field_id]
    gate_rows(sel, requested_category=requested_category)   # raises on any violation

    values = [int(r["value_i64"]) for r in sel]
    n = len(values)
    if op == "count":
        payload = {"n": n, "value": str(n), "bins": None}
    elif op == "sum":
        payload = {"n": n, "value": str(sum(values)), "bins": None}
    elif op == "mean":
        # fixed-point milli — no IEEE float in the attested surface
        milli = (sum(values) * 1000 // n) if n else 0
        payload = {"n": n, "value": str(milli), "scale": "milli", "bins": None}
    elif op == "p50":
        s = sorted(values)
        med = s[(n - 1) // 2] if n else 0        # integer lower-median (deterministic)
        payload = {"n": n, "value": str(med), "bins": None}
    else:  # hist — discrete value histogram (e.g. verdict_class enum)
        bins: dict[str, int] = {}
        for v in values:
            bins[str(v)] = bins.get(str(v), 0) + 1
        payload = {"n": n, "value": None, "bins": dict(sorted(bins.items()))}

    leaves = [row_commitment(r) for r in sel]
    return {
        "statistic": {"op": op, "field_id": field_id, "payload": payload},
        # leaves emitted SORTED (grok round-3): the root is over sorted leaves, so the buyer must see the
        # same order to re-derive by pairwise-hashing without guessing the sort.
        "input_commitment_set": {"algo": "sha256-sorted-leaf-merkle-v0",
                                 "root": _merkle_root(leaves), "n": n, "leaves": sorted(leaves)},
        "applet_version": {"crate": "w3bstream_applet", "semver": applet_semver, "wasm_sha256": wasm_sha256},
        "ceiling": ("statistic over consented exports only; consent bound in each row commitment; "
                    "cross-gamer requires per-row cross_aggregate_ok; non-biometric allowlist fields only; "
                    "the applet attests format+aggregation, not that the published export is truthful"),
    }
