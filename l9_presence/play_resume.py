"""UC-4 -- The verified play-resume (qortroller-play-resume-v0).

The gamer's cryptographic play history in one portable document: per-session rows rolled up from
artifacts that ALREADY exist (KAS kill-authorship records, PoSP synchronized-presence records,
deferred-attestation recoveries), REFERENCE-AND-BIND style -- every row cites its source file by
path + SHA-256, and the verifier re-hashes + re-extracts to confirm the resume faithfully
summarizes what it cites. The provable version of a stats-site profile.

DESIGN DISCIPLINE (PoSP/PORT-CERT precedent, D-CERT-6): schema string only -- NO new FROZEN-v1
family, NO domain tag, NO commitment method. Integrity derives from the cited artifacts. What
this verifier proves is SUMMARY-INTEGRITY (the resume cites real, untampered artifacts and
copies their fields faithfully); the underlying cryptography is proven by each artifact's OWN
verifier (KAS commitment verify, PoSP, verify_deferred_record, PORT-CERT) -- stated in notes,
never overclaimed.

CLAIM CEILING (mandatory block, test-pinned): counts and verdicts only -- advisory, not
population-certified, not identity-certified, NO rank/skill-ranking claims, developer_self scope.

Authored accounting honesty: live KAS and deferred attest the SAME kills through different
windows -- per-session `authored_best = max(live, deferred)`, NEVER the sum (double-count rail).
Pure stdlib; I/O lives in scripts/build_play_resume.py.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

SCHEMA = "qortroller-play-resume-v0"

# The ceiling block every resume MUST carry verbatim (test-pinned; UC-4 claim ceiling).
CEILING = {
    "advisory": True,
    "population_certified": False,
    "identity_certified": False,
    "rank_claim": "NONE — counts and verdicts only",
    "scope": "developer_self",
}

_KIND_FIELDS = {
    # kind -> fields copied into the row (and re-extracted at verify)
    "kas": ("verdict", "authored_kills", "own_deaths", "commitment", "span_ms"),
    "posp": ("verdict",),
    "deferred": ("verdict", "deferred_authored", "window_latency_pad_ms", "source_kas_commitment"),
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _session_key(doc: dict) -> Optional[str]:
    """U1 join key; session_display fallback for pre-U1 artifacts. None -> unjoinable (skipped
    with a note; never guessed)."""
    return doc.get("session_id") or doc.get("session_display") or None


def build_play_resume(sources: list, *, handle: Optional[str] = None,
                      generated_at: str = "") -> dict:
    """Assemble the resume from loaded sources: [{kind, path, sha256, doc}, ...].

    Groups by session join key; one row per session; duplicate (kind, session) keeps the FIRST
    and appends a note (fail-open, never silently overwrites). Unjoinable docs are counted in
    notes, never fabricated into rows."""
    rows: dict = {}
    notes: list = []
    skipped_unjoinable = 0
    for s in sources:
        kind, doc = s.get("kind"), s.get("doc") or {}
        if kind not in _KIND_FIELDS:
            notes.append(f"unknown source kind {kind!r} skipped: {s.get('path')}")
            continue
        key = _session_key(doc)
        if key is None:
            skipped_unjoinable += 1
            continue
        row = rows.setdefault(key, {"session": doc.get("session_display") or key,
                                    "session_id": doc.get("session_id"),
                                    "span_ms": doc.get("span_ms")})
        if kind in row:
            notes.append(f"duplicate {kind} for session {row['session']!r} "
                         f"ignored: {s.get('path')}")
            continue
        entry = {f: doc.get(f) for f in _KIND_FIELDS[kind]}
        entry["ref"] = {"path": s.get("path"), "sha256": s.get("sha256")}
        row[kind] = entry
        if row.get("span_ms") is None and doc.get("span_ms") is not None:
            row["span_ms"] = doc.get("span_ms")
    if skipped_unjoinable:
        notes.append(f"{skipped_unjoinable} artifact(s) lacked session_id/session_display "
                     "(pre-U1) — skipped, never guessed")

    ordered = [rows[k] for k in sorted(rows, key=lambda k: str(rows[k].get("session")))]
    live_total = sum(int((r.get("kas") or {}).get("authored_kills") or 0) for r in ordered)
    deferred_total = sum(int((r.get("deferred") or {}).get("deferred_authored") or 0)
                         for r in ordered)
    best_total = sum(max(int((r.get("kas") or {}).get("authored_kills") or 0),
                         int((r.get("deferred") or {}).get("deferred_authored") or 0))
                     for r in ordered)
    synchronized = sum(1 for r in ordered
                       if (r.get("posp") or {}).get("verdict") == "SYNCHRONIZED")
    return {
        "schema": SCHEMA,
        "handle": handle,
        "generated_at": generated_at,
        "ceiling": dict(CEILING),
        "totals": {
            "sessions": len(ordered),
            "posp_synchronized": synchronized,
            "authored_kills_live": live_total,
            "authored_kills_deferred": deferred_total,
            # max-per-session, never the sum: live + deferred attest the SAME kills.
            "authored_kills_best": best_total,
        },
        "sessions": ordered,
        "notes": notes + [
            "summary-integrity only: each row cites its source (path+sha256); the underlying "
            "cryptographic verification lives in each artifact's own verifier "
            "(KAS / PoSP / verify_deferred_record / PORT-CERT).",
            "authored_kills_best = per-session max(live, deferred) — the two paths attest the "
            "same kills through different windows; summing would double-count.",
        ],
    }


def verify_play_resume(resume: dict, load_bytes) -> dict:
    """Summary-integrity verifier. `load_bytes(path) -> bytes|None` is INJECTED (the I/O blast
    radius stays in the runner). Checks, fail-closed: schema + ceiling verbatim; every cited
    ref exists + sha256 matches; every copied field equals the cited doc's value; totals
    re-derive. Returns {ok, checks:[{name, ok, note}]}."""
    checks: list = []

    def _chk(name: str, ok: bool, note: str = "") -> bool:
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    ok = _chk("schema", resume.get("schema") == SCHEMA, f"schema={resume.get('schema')!r}")
    ok &= _chk("ceiling_verbatim", resume.get("ceiling") == CEILING,
               "ceiling block must match CEILING exactly (claim-ceiling rail)")
    live = deferred = best = sync = 0
    for r in resume.get("sessions", []):
        label = r.get("session", "?")
        for kind, fields in _KIND_FIELDS.items():
            entry = r.get(kind)
            if entry is None:
                continue
            ref = entry.get("ref") or {}
            raw = load_bytes(ref.get("path")) if ref.get("path") else None
            if raw is None:
                ok &= _chk(f"{label}:{kind}:ref_present", False,
                           f"cited file missing: {ref.get('path')}")
                continue
            ok &= _chk(f"{label}:{kind}:sha256", sha256_bytes(raw) == ref.get("sha256"),
                       "cited file hash must match ref.sha256 (tamper rail)")
            try:
                doc = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001 -- unparseable cited doc is a hard fail
                ok &= _chk(f"{label}:{kind}:parse", False, "cited file not valid JSON")
                continue
            drift = [f for f in fields if entry.get(f) != doc.get(f)]
            ok &= _chk(f"{label}:{kind}:fields", not drift,
                       f"row fields must equal cited doc: drift={drift}" if drift else "")
        live += int((r.get("kas") or {}).get("authored_kills") or 0)
        deferred += int((r.get("deferred") or {}).get("deferred_authored") or 0)
        best += max(int((r.get("kas") or {}).get("authored_kills") or 0),
                    int((r.get("deferred") or {}).get("deferred_authored") or 0))
        sync += 1 if (r.get("posp") or {}).get("verdict") == "SYNCHRONIZED" else 0
    t = resume.get("totals") or {}
    ok &= _chk("totals_rederive",
               (t.get("sessions") == len(resume.get("sessions", []))
                and t.get("authored_kills_live") == live
                and t.get("authored_kills_deferred") == deferred
                and t.get("authored_kills_best") == best
                and t.get("posp_synchronized") == sync),
               "totals must re-derive from rows")
    return {"ok": bool(ok), "checks": checks}
