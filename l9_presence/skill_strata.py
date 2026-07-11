"""UC-2 -- Skill-strata harness (qortroller-skill-strata-v0).

Stratifies SESSIONS into demonstration-quality bands from protocol verdicts already computed --
the curriculum-learning consumer's need ("which demonstrations are authorship-verified and
combat-dense?") answered with labels, not raw data. Input is the VERIFIED PLAY-RESUME (UC-4):
strata are a PURE, DETERMINISTIC function of that document, so the labels inherit the resume's
citation chain and the verifier is simply re-derivation (recompute bands from the cited resume,
byte-compare). No DB, no biometrics touched, nothing new measured.

THE LOAD-BEARING HONESTY DISTINCTION (test-pinned): bands grade SESSIONS AS DEMONSTRATIONS
(data-quality strata for corpus buyers), NEVER PLAYERS AS RANKS. No ELO, no matchmaking, no
cross-player comparison -- the population gate stands. A band says "this session is an
authorship-verified, high-combat-density demonstration", not "this player is good".

BAND RULES v0 (first match wins; deterministic; the methodology block ships verbatim in output):
  EXCLUDED_INTEGRITY     kas verdict in {HYGIENE_FAIL, UNVERIFIABLE} -- never enters a corpus
  AUTHORED_HIGH_DENSITY  live AUTHORED_SESSION AND density >= 0.8 authored-kills/min (v0
                         PROVISIONAL threshold -- declared, configurable, revisit with data)
  AUTHORED_STANDARD      live AUTHORED_SESSION (below threshold / no usable span)
  AUTHORED_DEFERRED      not live-authored, but deferred DEFERRED_AUTHORED_SESSION (the
                         card-free recovery path -- same evidence, read later)
  PRESENCE_ONLY          PoSP SYNCHRONIZED with no authorship -- presence-verified filler,
                         usable where authorship is not required
  UNGRADED               everything else (honest catch-all; never silently promoted)

WMP hook: `wmp_metadata(band)` returns the additive extra_metadata fields for a future WMP
Phase-2 bundle (strata ride as labels on post-phi bundles; nothing here edits the assembler).
Pure stdlib; I/O lives in scripts/build_skill_strata.py.
"""
from __future__ import annotations

from typing import Optional

from l9_presence.play_resume import CEILING as _RESUME_CEILING
from l9_presence.play_resume import sha256_bytes  # noqa: F401 (re-export for runner symmetry)

SCHEMA = "qortroller-skill-strata-v0"
DEFAULT_HIGH_DENSITY_KPM = 0.8          # v0 PROVISIONAL -- authored kills per minute

BANDS = ("EXCLUDED_INTEGRITY", "AUTHORED_HIGH_DENSITY", "AUTHORED_STANDARD",
         "AUTHORED_DEFERRED", "PRESENCE_ONLY", "UNGRADED")

# UC-2 ceiling = the resume ceiling + the no-rank distinction made explicit for this artifact.
CEILING = dict(_RESUME_CEILING)
CEILING["strata_semantics"] = ("SESSION demonstration-quality bands ONLY — never player rank, "
                               "never ELO, never cross-player comparison (population gate)")

METHODOLOGY = {
    "version": "v0-provisional",
    "input": "qortroller-play-resume-v0 (UC-4) — strata are a pure function of the resume",
    "density_metric": "authored_kills_best / session_minutes (span_ms end-start)",
    "high_density_threshold_kpm": DEFAULT_HIGH_DENSITY_KPM,
    "rule_order": "EXCLUDED_INTEGRITY > AUTHORED_HIGH_DENSITY > AUTHORED_STANDARD > "
                  "AUTHORED_DEFERRED > PRESENCE_ONLY > UNGRADED (first match wins)",
    "note": "thresholds are DECLARED and provisional; changing them changes the schema-minor "
            "version, never silently",
}


def _density_kpm(row: dict) -> Optional[float]:
    """authored_best / minutes from the resume row; None when span is absent/degenerate."""
    span = row.get("span_ms")
    if not (isinstance(span, (list, tuple)) and len(span) == 2):
        return None
    try:
        minutes = (float(span[1]) - float(span[0])) / 60_000.0
    except (TypeError, ValueError):
        return None
    if minutes <= 0:
        return None
    live = int((row.get("kas") or {}).get("authored_kills") or 0)
    deferred = int((row.get("deferred") or {}).get("deferred_authored") or 0)
    return max(live, deferred) / minutes


def band_for_row(row: dict, *, high_density_kpm: float = DEFAULT_HIGH_DENSITY_KPM) -> str:
    """The deterministic band rule (first match wins). Pure; pinned by re-derivation verify."""
    kas_v = (row.get("kas") or {}).get("verdict")
    if kas_v in ("HYGIENE_FAIL", "UNVERIFIABLE"):
        return "EXCLUDED_INTEGRITY"
    dens = _density_kpm(row)
    if kas_v == "AUTHORED_SESSION":
        if dens is not None and dens >= float(high_density_kpm):
            return "AUTHORED_HIGH_DENSITY"
        return "AUTHORED_STANDARD"
    if (row.get("deferred") or {}).get("verdict") == "DEFERRED_AUTHORED_SESSION":
        return "AUTHORED_DEFERRED"
    if (row.get("posp") or {}).get("verdict") == "SYNCHRONIZED":
        return "PRESENCE_ONLY"
    return "UNGRADED"


def build_strata_report(resume: dict, *, resume_path: str = "", resume_sha256: str = "",
                        high_density_kpm: float = DEFAULT_HIGH_DENSITY_KPM,
                        generated_at: str = "") -> dict:
    """Assemble the strata report from a loaded play-resume. REFERENCE-AND-BIND: the report
    cites the resume by path+sha256; every label re-derives from it deterministically."""
    rows = []
    dist = {b: 0 for b in BANDS}
    for r in resume.get("sessions", []):
        band = band_for_row(r, high_density_kpm=high_density_kpm)
        dens = _density_kpm(r)
        dist[band] += 1
        rows.append({"session": r.get("session"), "session_id": r.get("session_id"),
                     "band": band,
                     "density_kpm": round(dens, 3) if dens is not None else None,
                     "kas_verdict": (r.get("kas") or {}).get("verdict"),
                     "deferred_verdict": (r.get("deferred") or {}).get("verdict"),
                     "posp_verdict": (r.get("posp") or {}).get("verdict")})
    corpus_eligible = sum(v for b, v in dist.items()
                          if b in ("AUTHORED_HIGH_DENSITY", "AUTHORED_STANDARD",
                                   "AUTHORED_DEFERRED", "PRESENCE_ONLY"))
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "ceiling": dict(CEILING),
        "methodology": {**METHODOLOGY, "high_density_threshold_kpm": float(high_density_kpm)},
        "resume_ref": {"path": resume_path, "sha256": resume_sha256,
                       "schema": resume.get("schema")},
        "distribution": dist,
        "corpus_eligible_sessions": corpus_eligible,
        "sessions": rows,
        "notes": [
            "strata are a pure function of the cited resume — verify = re-derive + compare",
            "EXCLUDED_INTEGRITY and UNGRADED sessions never enter demonstration corpora",
            "bands label sessions as demonstrations; they say nothing about the player",
        ],
    }


def verify_strata_report(report: dict, load_bytes) -> dict:
    """Re-derivation verifier (fail-closed): the cited resume must exist + hash-match, be the
    right schema, and re-running the pure band rules over it must reproduce EVERY row and the
    distribution. `load_bytes(path) -> bytes|None` injected (I/O stays in the runner)."""
    import json as _json
    checks: list = []

    def _chk(name: str, ok: bool, note: str = "") -> bool:
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    ok = _chk("schema", report.get("schema") == SCHEMA, f"schema={report.get('schema')!r}")
    ok &= _chk("ceiling_verbatim", report.get("ceiling") == CEILING,
               "ceiling must match CEILING exactly (no-rank rail)")
    ref = report.get("resume_ref") or {}
    raw = load_bytes(ref.get("path")) if ref.get("path") else None
    if raw is None:
        ok &= _chk("resume_present", False, f"cited resume missing: {ref.get('path')}")
        return {"ok": False, "checks": checks}
    ok &= _chk("resume_sha256", sha256_bytes(raw) == ref.get("sha256"),
               "cited resume hash must match (tamper rail)")
    try:
        resume = _json.loads(raw.decode("utf-8"))
    except Exception:  # noqa: BLE001
        ok &= _chk("resume_parse", False, "cited resume not valid JSON")
        return {"ok": False, "checks": checks}
    thr = float((report.get("methodology") or {}).get("high_density_threshold_kpm",
                                                      DEFAULT_HIGH_DENSITY_KPM))
    rederived = build_strata_report(resume, resume_path=ref.get("path", ""),
                                    resume_sha256=ref.get("sha256", ""),
                                    high_density_kpm=thr,
                                    generated_at=report.get("generated_at", ""))
    ok &= _chk("rows_rederive", rederived["sessions"] == report.get("sessions"),
               "every band label must re-derive from the cited resume")
    ok &= _chk("distribution_rederive", rederived["distribution"] == report.get("distribution"),
               "distribution must re-derive")
    ok &= _chk("corpus_eligible_rederive",
               rederived["corpus_eligible_sessions"] == report.get("corpus_eligible_sessions"),
               "corpus-eligible count must re-derive")
    return {"ok": bool(ok), "checks": checks}


def wmp_metadata(band: str) -> dict:
    """The additive extra_metadata fields a future WMP Phase-2 bundle carries (UC-2 -> UC-1
    hook). Labels only — nothing biometric, nothing forbidden (the assembler's
    DataFloorViolationError guard still applies downstream)."""
    if band not in BANDS:
        raise ValueError(f"unknown band {band!r}")
    return {"skill_strata_band": band, "skill_strata_schema": SCHEMA,
            "skill_strata_semantics": "session-demonstration band, not player rank"}
