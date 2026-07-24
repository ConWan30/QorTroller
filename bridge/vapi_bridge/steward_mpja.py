"""A2A-STEWARD-EVOLVE B2 — Sentry MPJA (Multi-Surface Provenance Join Attestor).

Sentry's O3 authority is pda-attestation-anchor. Drafting "one more anchor per new root" is volume, not
evolution. The post-May novelty is the JOIN: a single `session_id` ties KAS authorship / PoSP presence /
node-contribution-ledger / scorecard root / W3bstream mechanical verify (and optionally a WMP bundle
root). MPJA v0 attests the COMPLETENESS of that join plus a set of STRUCTURAL false-claim rails — "are all
the provenance surfaces present, and does none of them claim a state its own evidence can't back?" — not
"is one hash on chain."

HONEST SCOPE (grok round-05): v0 is completeness + structural rails ONLY. It does NOT yet verify
cross-surface CONTENT consistency — session_id match across surfaces, kas-commitment ↔ posp-root binding,
"SYNCHRONIZED-but-KAS-absent" as a contradiction — those are v0.1. A JOIN_COMPLETE therefore means "every
required surface is present and none is structurally false-claiming," NOT "the surfaces agree on content."

It emits a DRAFT join attestation (`draft://attestations/join/{session_id}`) with a completeness bitmap,
a join verdict, what's missing, and a completeness-certificate preimage (a hash over the presence-bitmap +
roots — NOT a content-bound join root; binding the actual surface commitments is v0.1). The actual
PDA/on-chain anchor stays TWO-KEY + estimate-first via Sentry's existing live-write executor — MPJA never
anchors, never spends IOTX. Gated by `cfg.mpja_enabled` (default False).

Load-bearing honesty rail (grok): a ledger entry claiming ANCHORED without a hex-shaped anchor tx is
JOIN_BROKEN (the false-anchored footgun, caught mechanically — never attest a claim the evidence can't
back).
"""
from __future__ import annotations

import hashlib

SCHEMA = "qortroller-mpja-v0"
_DOMAIN = b"VAPI-MPJA-JOIN-v0"
JOIN_VERDICTS = ("JOIN_COMPLETE", "JOIN_PARTIAL", "JOIN_BROKEN")

# the surfaces that constitute a whole join (ANCHORED + WMP root are optional — a complete join can be
# pre-anchor and need not carry a marketplace bundle).
_REQUIRED = ("kas_present", "posp_present", "posp_synchronized", "ledger_entry_present",
             "scorecard_root_bound", "w3s_mechanical_ok")


def _is_hexish(s) -> bool:
    """Hex-shaped identifier check. Strips an optional `0x` prefix (real IoTeX roots/tx hashes carry it,
    grok round-05) and requires >= 16 hex chars so garbage like 'not-a-tx' or a bare '0x' fails closed."""
    if not isinstance(s, str):
        return False
    t = s[2:] if s[:2].lower() == "0x" else s
    return len(t) >= 16 and all(c in "0123456789abcdefABCDEF" for c in t)


def evaluate_join(*, session_id: str, kas_verdict: str | None = None, posp_verdict: str | None = None,
                  ledger_status: str | None = None, ledger_anchor_tx: str | None = None,
                  scorecard_root: str | None = None, w3s_mechanical_ok: bool | None = None,
                  wmp_root: str | None = None) -> dict:
    """Pure join-completeness evaluator over one session's provenance surfaces. Draft only."""
    bitmap = {
        "kas_present": bool(kas_verdict),
        "posp_present": bool(posp_verdict),
        "posp_synchronized": (str(posp_verdict).upper() == "SYNCHRONIZED"),
        "ledger_entry_present": bool(ledger_status),
        "ledger_anchored": (str(ledger_status).upper() == "ANCHORED"),
        "scorecard_root_bound": _is_hexish(scorecard_root),
        "w3s_mechanical_ok": (w3s_mechanical_ok is True),
        "wmp_root_optional": _is_hexish(wmp_root),
    }

    # BROKEN = a surface claims a state the evidence does not back (never attest an unbacked claim).
    broken_reasons = []
    if str(ledger_status).upper() == "ANCHORED":
        if not (ledger_anchor_tx and str(ledger_anchor_tx).strip()):
            broken_reasons.append("ledger claims ANCHORED with no anchor tx (false-anchored)")
        elif not _is_hexish(ledger_anchor_tx):
            broken_reasons.append("ledger claims ANCHORED with malformed anchor tx (not a tx hash)")
    if scorecard_root is not None and scorecard_root != "" and not _is_hexish(scorecard_root):
        broken_reasons.append("scorecard_root present but malformed (not hex)")
    if wmp_root is not None and wmp_root != "" and not _is_hexish(wmp_root):
        broken_reasons.append("wmp_root present but malformed (not hex)")

    missing = [k for k in _REQUIRED if not bitmap[k]]
    if broken_reasons:
        verdict = "JOIN_BROKEN"
    elif not missing:
        verdict = "JOIN_COMPLETE"
    else:
        verdict = "JOIN_PARTIAL"

    # the preimage Sentry WOULD anchor (two-key) — only proposed for a whole, non-contradictory join.
    proposed_anchor_preimage_hash = None
    if verdict == "JOIN_COMPLETE":
        bits = "".join("1" if bitmap[k] else "0" for k in sorted(bitmap))
        body = (_DOMAIN + b"|" + str(session_id).encode() + b"|" + bits.encode() + b"|"
                + (scorecard_root or "").encode() + b"|" + (wmp_root or "").encode())
        proposed_anchor_preimage_hash = hashlib.sha256(body).hexdigest()

    return {
        "schema": SCHEMA,
        "steward": "sentry",
        "task": "MPJA",
        "session_id": session_id,
        "completeness_bitmap": bitmap,
        "join_verdict": verdict,
        "missing": missing,
        "broken_reasons": broken_reasons,
        "proposed_anchor_preimage_hash": proposed_anchor_preimage_hash,
        "note": "DRAFT ONLY — Sentry drafts the join attestation; the PDA/on-chain anchor stays TWO-KEY + "
                "estimate-first via the existing executor. MPJA never anchors, never spends IOTX. A "
                "JOIN_BROKEN (e.g. ANCHORED-without-tx) is NEVER proposed for anchoring. v0 = completeness "
                "+ structural false-claim rails only; cross-surface CONTENT consistency (session_id match, "
                "commitment<->root binding) is v0.1. The preimage is a completeness-certificate hash over "
                "the presence-bitmap + roots, NOT a content-bound join root.",
    }


def attest_joins_from_store(store, cfg, *, session_ids: list[str] | None = None,
                            limit: int = 200) -> dict:  # pragma: no cover - read-only adapter STUB
    """Read-only Store adapter, gated by cfg.mpja_enabled (default False).

    HONEST SCOPE (grok round-05, mirrors the B1 scan_repo round-04 fix): this is a STUB. It does NOT yet
    pull the real surfaces from the Store — no node_contribution_ledger / PoSP audits / scorecard-root /
    W3bstream extraction is wired. Feeding it a bare session_id list would only produce hollow all-missing
    PARTIALs, which would be a false 'working join product', so the stub REFUSES to invent drafts and
    returns an explicit stub marker instead. The pure `evaluate_join()` evaluator is real and tested; this
    Store adapter is v0.1 work. Never git, never chain, never spend."""
    if not bool(getattr(cfg, "mpja_enabled", False)):
        return {"schema": SCHEMA, "enabled": False, "note": "mpja_enabled=False (opt-in capability)"}
    return {"schema": SCHEMA, "enabled": True, "steward": "sentry", "task": "MPJA",
            "n_drafts": 0, "drafts": [],
            "adapter_scope": "STUB — session_id list only; no ledger/PoSP/scorecard/W3S Store extraction "
                             "(v0.1). The pure evaluate_join() evaluator works; this adapter does not yet.",
            "note": "STUB adapter — refuses to emit hollow PARTIALs from unresolved surfaces. Wire real "
                    "Store extraction in v0.1. draft-only; anchor two-key; no IOTX; no git/chain write."}
