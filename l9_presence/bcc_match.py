"""BCC Match — sealed gamer-local match-presence corpus (A1-b). qortroller-bcc-match-artifact-v0.

THE CLAIM: "for ONE match/session (the U1 session_id), a MULTI-SURFACE presence assertion
(PoSP SYNCHRONIZED + KAS/deferred authorship clearing a coherence floor) is accumulated into a
sealed, gamer-local, provenance-chained corpus — a SECOND BCC family, match-bound, that grows
the developer's own certified-session pile WITHOUT touching any proven number and WITHOUT
poisoning the L9 coupling lane (bcc_l9/) or tournament L4/AIT state."

WHY A SEPARATE LANE (D-A1b-1 kill-check): L9 sub-lane A harvests a 3-feature COUPLING vector
(_SEP_FEATURES = dominant_coupling / yaw_pitch_ratio / yaw_decoupled). The match flow is a
MULTI-SURFACE presence object (PoSP / KAS / archive). Mapping one into the other (13->3, PCA,
first-3) is a category error that silently breaks readers assuming bcc_l9 payloads are 3-dim. So
Match is its OWN store (bcc_match/), its OWN candidate genesis tag, its OWN typed payload — never
bcc_l9 with a third sub_lane. Isolation over clever reuse: the parallel BCCMatchStore below is
deliberate duplication so the "different lane" property is STRUCTURAL, not a comment.

REFERENCE-AND-BIND (PoSP / KAS / kas_deferred precedent, D-CERT-6 discipline): NO new domain-tag
hash, NO new commitment primitive, NO FROZEN-v1 family. A schema string + a CANDIDATE chain lane
tag only (QORTROLLER-BCC-MATCH-GENESIS-v0 — a candidate lane tag, NOT a registered PATTERN-017
family, exactly as bcc_l9's QORTROLLER-BCC-GENESIS-v0; NOT a PV-CI invariant). Integrity derives
from what the artifact REFERENCES: the PoSP verdict + commitments, the KAS/deferred commitments,
the archive manifest SHA-256s, the NAMED events_roots. The chain digests an ALREADY-BUILT
artifact; it computes no PoSP/KAS/L4 itself.

v0 SCOPE — NONE-ONLY (F-A1b-AUDIT-1): the L4 13-feature attachment (design §5.2/§5.3) is DEFERRED
to artifact-v1. The pre-implementation audit found the design's §2.4 key list matched NO real
bridge FEATURE_KEYS constant (behavioral_archaeologist.FEATURE_KEYS is 9 keys in a different
order; continuity_prover/pitl_prover differ again), so pinning a 13-key vector now would pin a
phantom. v0 admits presence rows with feature_contract.name="NONE", dim=0 — ASSERTION-PLANE ONLY,
zero controller-internal biometrics. This strengthens corpus purity; the L4 attach returns in
artifact-v1 pinned against a real `import FEATURE_KEYS`. record() REFUSES a non-NONE contract.

ADMISSION IS FAIL-CLOSED (design §6, G1..G8): only PoSP SYNCHRONIZED (never PARTIAL/UNVERIFIABLE);
authorship non-empty (live AUTHORED_SESSION or deferred DEFERRED_AUTHORED_SESSION, authored>=1);
coherence_fraction >= floor (0.50 pre-registered, NOT retuned in a harvest PR); no inherited
HYGIENE_FAIL/UNVERIFIABLE; surface session_ids consistent (anti-assertion, PoSP precedent).
M15-class (0 authored / link-flip) and M16-class (HYGIENE_FAIL) NEVER enter. NOMINAL-only writes
(DEGRADED specified for forward-compat, rejected in v0). The GATE is fail-CLOSED (any miss ->
reject, no partial write); the HOST (runner / optional session-close hook) is fail-OPEN (a harvest
error never breaks session close).

PER-MATCH ROWS INHERIT A SESSION-SCOPED PoSP (D-A1b-6): PoSP is issued per session_id, not per
match span. A per-match row carries the session's SYNCHRONIZED verdict (G2, session-scope) with
per-span coherence/authorship (G4/G5, span-scope). The runner slices multi-match sessions via
kas_deferred.slice_scan_by_spans; this module is per-row agnostic (takes explicit
authored/eligible ints).

ISOLATION (BCC_SCOPE.md, specialized): writes ONLY to bcc_match/; never writes/calls
separation_defensibility_log / AIT / L4 thresholds / PoEP bands / behavioral_lattice / bcc_l9.
Parallel to GIC/WEC/CORPUS-SNAPSHOT, never a link in them. Promotion is a separate reviewed export
that re-runs analyses from scratch, NEVER a live read of bcc_match/ from tournament code. Default-
OFF (BCCMatchConfig.enabled=False -> fully dormant). PURE stdlib — no bridge/numpy/chain imports.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Optional

BCC_MATCH_GENESIS_TAG = b"QORTROLLER-BCC-MATCH-GENESIS-v0"   # CANDIDATE lane tag — NOT registered
MATCH_ARTIFACT_SCHEMA = "qortroller-bcc-match-artifact-v0"    # schema string — NOT a domain tag
ARTIFACT_TYPE = "match_presence"                             # hard discriminator (readers filter on this)

MATCH_PRESENCE = 0x01     # sub-lane (match-local): a full MatchPresenceArtifact
# 0x02 reserved for a future MATCH_REFLEX lane (NOT PoEP lane B) — unused in v0

_Q_NOMINAL = 0x01
_Q_DEGRADED = 0x10        # forward-compat only; v0 rejects rather than writes DEGRADED (§6.3)

DEFAULT_COHERENCE_FLOOR = 0.50    # pre-registered (§6.2) — do NOT retune inside a harvest PR
DEFAULT_K_FLOOR = 3               # mirrors kas_deferred.DEFAULT_K_FLOOR
DEFAULT_MIN_KILLS = 2             # mirrors kill_authorship_session.DEFAULT_MIN_KILLS

# assertion-plane verdict strings this lane BINDS to (imported semantics; never re-minted here)
_POSP_SYNCHRONIZED = "SYNCHRONIZED"
_KAS_AUTHORED_SESSION = "AUTHORED_SESSION"
_DEFERRED_AUTHORED_SESSION = "DEFERRED_AUTHORED_SESSION"
_HYGIENE_FAIL = "HYGIENE_FAIL"
_UNVERIFIABLE = "UNVERIFIABLE"


# ----------------------------------------------------------------------------- chain primitives
def canonical_digest(payload: dict) -> str:
    """Deterministic SHA-256 of a payload (sort_keys -> order-independent). Same discipline as
    bcc.canonical_digest; the artifact is opaque to the chain."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def genesis_bcc_match() -> str:
    return hashlib.sha256(BCC_MATCH_GENESIS_TAG).hexdigest()


def compute_bcc_match_hash(prev_hex: str, feature_digest_hex: str, quality_code: int,
                           sub_lane: int, ts_ns: int) -> str:
    """Formula-twin of bcc.compute_bcc_hash (BYTE-IDENTICAL preimage layout so tooling reuses),
    over a DIFFERENT genesis so the two lanes cannot be concatenated by accident (D-A1b-2):
    SHA-256(prev(32) || feature_digest(32) || quality(1) || sub_lane(1) || ts_ns_be(8))."""
    h = hashlib.sha256()
    h.update(bytes.fromhex(prev_hex))
    h.update(bytes.fromhex(feature_digest_hex))
    h.update(int(quality_code).to_bytes(1, "big"))
    h.update(int(sub_lane).to_bytes(1, "big"))
    h.update(int(ts_ns).to_bytes(8, "big"))
    return h.hexdigest()


class BCCMatchStore:
    """Append-only JSONL chain in the sealed match lane. The ONLY thing this module writes to.
    Parallel to bcc.BCCStore by design (isolation over reuse) — own genesis, own chain file."""

    def __init__(self, out_dir: str = "bcc_match") -> None:
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.path = os.path.join(out_dir, "bcc_match_chain.jsonl")

    def load(self) -> list:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def append(self, payload: dict, quality_code: int, sub_lane: int,
               ts_ns: Optional[int] = None) -> dict:
        recs = self.load()
        last = recs[-1] if recs else None
        prev = last["bcc_match_hash"] if last else genesis_bcc_match()
        ts_ns = ts_ns if ts_ns is not None else time.time_ns()
        if last and ts_ns <= last["ts_ns"]:            # monotonicity guard (INV-GIC-002 analog)
            ts_ns = last["ts_ns"] + 1
        fdig = canonical_digest(payload)
        bcc_hash = compute_bcc_match_hash(prev, fdig, quality_code, sub_lane, ts_ns)
        rec = {"seq": (last["seq"] + 1 if last else 0), "prev_hash": prev,
               "bcc_match_hash": bcc_hash, "feature_digest": fdig,
               "quality_code": quality_code, "sub_lane": sub_lane, "ts_ns": ts_ns,
               "payload": payload}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return rec

    def verify(self) -> bool:
        prev = genesis_bcc_match()
        for r in self.load():
            if r["prev_hash"] != prev:
                return False
            if canonical_digest(r["payload"]) != r["feature_digest"]:   # payload tamper -> mismatch
                return False
            if compute_bcc_match_hash(prev, r["feature_digest"], r["quality_code"],
                                      r["sub_lane"], r["ts_ns"]) != r["bcc_match_hash"]:
                return False
            prev = r["bcc_match_hash"]
        return True

    def status(self) -> dict:
        recs = self.load()
        return {"chain_length": len(recs), "chain_intact": self.verify(),
                "head": recs[-1]["bcc_match_hash"] if recs else None,
                "match_presence": sum(1 for r in recs if r["sub_lane"] == MATCH_PRESENCE)}


@dataclass
class BCCMatchConfig:
    enabled: bool = False                              # dormant by default — flip on to accumulate
    out_dir: str = "bcc_match"
    coherence_floor: float = DEFAULT_COHERENCE_FLOOR
    k_floor: int = DEFAULT_K_FLOOR
    min_kills: int = DEFAULT_MIN_KILLS


# ----------------------------------------------------------------------------- coherence + admission
def coherence_fraction(authored_clusters: int, eligible_clusters: int) -> float:
    """authored / max(1, eligible). authored ⊆ eligible (an authored cluster meets the K-floor,
    so it is eligible) ⇒ fraction ∈ [0, 1]. The max(1,·) guard is dead-but-harmless: it only
    bites at authored=0, which G5 already rejects. (§6.2)"""
    return int(authored_clusters) / max(1, int(eligible_clusters))


def _authorship_tier(kas: Optional[dict], deferred: Optional[dict]) -> str:
    live = (kas or {}).get("verdict") == _KAS_AUTHORED_SESSION
    dfrd = (deferred or {}).get("verdict") == _DEFERRED_AUTHORED_SESSION
    if live and dfrd:
        return "BOTH"
    if live:
        return "LIVE"
    if dfrd:
        return "DEFERRED"
    return "NONE"          # unreachable once admission (G5) has passed — defensive


def _posp_commitment_refs(posp: Optional[dict]) -> dict:
    """Pull the reference (not the evidence) commitments out of the PoSP record."""
    refs: dict = {}
    kas = (posp or {}).get("kas") or {}
    if kas.get("commitment"):
        refs["kas"] = kas["commitment"]
    fusion = (posp or {}).get("fusion") or {}
    fr = fusion.get("record_hashes") or []
    if fr:
        refs["fusion"] = fr[:8]            # references, capped — never the full evidence list
    arch = (posp or {}).get("archive") or {}
    if arch.get("dir"):
        refs["archive"] = arch["dir"]
    return refs


def passes_match_admission(*, session_id: Optional[str], posp: Optional[dict],
                           kas: Optional[dict], deferred: Optional[dict],
                           authored_clusters: int, eligible_clusters: int,
                           coherence_floor: float = DEFAULT_COHERENCE_FLOOR) -> tuple:
    """Fail-closed gate G1..G6 (G7 enabled + G8 store-path are harvester/store concerns).
    Returns (ok: bool, reasons: list[str]). ANY reason -> reject; never a partial write."""
    reasons: list = []

    # G1 — session_id present (the U1 join key)
    if not session_id:
        reasons.append("G1: empty session_id (U1 join key)")

    # G2 — PoSP SYNCHRONIZED only (PARTIAL_SURFACES / UNVERIFIABLE rejected)
    pv = (posp or {}).get("verdict")
    if pv != _POSP_SYNCHRONIZED:
        reasons.append(f"G2: PoSP verdict {pv!r} != SYNCHRONIZED")

    # G3 — PoSP surface-id clean: no MISMATCH note, and the PoSP wrapper id matches the artifact
    for n in (posp or {}).get("notes") or []:
        if "MISMATCH" in str(n):
            reasons.append("G3: PoSP notes carry a session_id MISMATCH")
            break
    psid = (posp or {}).get("session_id")
    if session_id and psid not in (None, "", session_id):
        reasons.append("G3: PoSP session_id != artifact session_id")

    # G5 — authorship non-empty (live AUTHORED_SESSION or deferred DEFERRED_AUTHORED_SESSION)
    live_authored = (kas or {}).get("verdict") == _KAS_AUTHORED_SESSION
    deferred_authored = (deferred or {}).get("verdict") == _DEFERRED_AUTHORED_SESSION
    if not (live_authored or deferred_authored) or int(authored_clusters) < 1:
        reasons.append("G5: no authored session (live/deferred) or authored_clusters < 1")

    # G6 — no inherited hygiene fail / unverifiable; surface session_ids consistent (anti-assertion)
    for name, rec in (("KAS", kas), ("deferred", deferred)):
        v = (rec or {}).get("verdict")
        if v in (_HYGIENE_FAIL, _UNVERIFIABLE):
            reasons.append(f"G6: inherited {name} verdict {v!r}")
        sid = (rec or {}).get("session_id")
        if sid not in (None, "", session_id):
            reasons.append(f"G6: {name} session_id mismatch vs artifact (anti-assertion)")

    # G4 — coherence floor (evaluated last so its number is always reported)
    frac = coherence_fraction(authored_clusters, eligible_clusters)
    if frac < coherence_floor:
        reasons.append(f"G4: coherence {frac:.3f} < floor {coherence_floor:.2f}")

    return (len(reasons) == 0, reasons)


def build_match_presence_artifact(*, session_id: Optional[str], session_display: Optional[str] = None,
                                  device_id: Optional[str] = None, player: str = "",
                                  span_ms=None, posp: Optional[dict], kas: Optional[dict] = None,
                                  deferred: Optional[dict] = None, authored_clusters: int,
                                  eligible_clusters: int, match_context: Optional[dict] = None,
                                  transport: Optional[str] = None,
                                  coherence_floor: float = DEFAULT_COHERENCE_FLOOR,
                                  advisory: bool = True) -> tuple:
    """Pure builder. Returns (artifact_dict, []) if admission passes, else (None, reasons).
    NEVER a partial write. v0 emits feature_contract.name="NONE" unconditionally (F-A1b-AUDIT-1)."""
    ok, reasons = passes_match_admission(
        session_id=session_id, posp=posp, kas=kas, deferred=deferred,
        authored_clusters=authored_clusters, eligible_clusters=eligible_clusters,
        coherence_floor=coherence_floor)
    if not ok:
        return None, reasons

    frac = coherence_fraction(authored_clusters, eligible_clusters)
    roots = (posp or {}).get("events_roots") or {}
    arch = (posp or {}).get("archive") or {}
    artifact = {
        "schema": MATCH_ARTIFACT_SCHEMA,
        "type": ARTIFACT_TYPE,
        "session_id": session_id,
        "session_display": session_display,
        "device_id": device_id,
        "player": player,                              # local label — NOT a population identity claim
        "span_ms": list(span_ms) if span_ms else None,
        "advisory": bool(advisory),                    # FROZEN default true in v0
        "cert_scope": "developer_self",                # FROZEN in v0
        "population_certified": False,                 # FROZEN false in v0
        "admission": {
            "posp_verdict": _POSP_SYNCHRONIZED,
            "posp_commitment_refs": _posp_commitment_refs(posp),
            "coherence_fraction": round(frac, 6),
            "coherence_numerator": int(authored_clusters),
            "coherence_denominator": int(eligible_clusters),
            "authorship_tier": _authorship_tier(kas, deferred),
            "quality_code": _Q_NOMINAL,
        },
        "assertion_refs": {                            # REFERENCE-AND-BIND — integrity lives here
            "kas_commitment": (kas or {}).get("commitment"),
            "kas_verdict": (kas or {}).get("verdict"),
            "deferred_verdict": (deferred or {}).get("verdict"),
            "deferred_authored": (deferred or {}).get("deferred_authored"),
            "posp_verdict": _POSP_SYNCHRONIZED,
            "kas_session_root": roots.get("kas_session_root"),
            "retina_perception_root": roots.get("retina_perception_root"),   # may be null honestly
            "archive_manifest_dir": arch.get("dir"),
            "archive_id_verified": bool(arch.get("id_verified")),
            "temporal_beacon": (posp or {}).get("temporal_beacon"),
        },
        "match_context": match_context or {"n_matches": None, "in_match_spans": [],
                                           "transport": transport},
        # v0 NONE-ONLY (F-A1b-AUDIT-1): assertion-plane only, zero controller-internal biometrics.
        # L4 attachment (design §5.2/§5.3) returns in artifact-v1, pinned to a real FEATURE_KEYS.
        "feature_contract": {"name": "NONE", "dim": 0, "keys": [], "vector": [],
                             "aggregate": None, "source": "unavailable"},
    }
    return artifact, []


class MatchHarvester:
    """Digests + chains an ALREADY-BUILT MatchPresenceArtifact into the sealed match lane. No-op
    while dormant. Touches nothing outside out_dir — structurally cannot mutate a proven number.
    Refuses (LOUD) anything that is not a v0 NONE-only match_presence artifact (poison rail §11.1)."""

    def __init__(self, cfg: Optional[BCCMatchConfig] = None) -> None:
        self.cfg = cfg or BCCMatchConfig()
        self.store = BCCMatchStore(self.cfg.out_dir)

    def record(self, artifact: dict) -> Optional[dict]:
        if not self.cfg.enabled:                       # G7 — dormant no-op
            return None
        # hard type discriminator: refuse an L9 payload or any non-match artifact (fails LOUD,
        # never silently mis-shaped into the match chain — the D-A1b-2 poison rail)
        if not isinstance(artifact, dict) or artifact.get("type") != ARTIFACT_TYPE \
                or artifact.get("schema") != MATCH_ARTIFACT_SCHEMA:
            raise ValueError("MatchHarvester.record: not a qortroller-bcc-match-artifact-v0 "
                             f"{ARTIFACT_TYPE} artifact")
        # v0 invariants: NONE-only feature contract; population_certified must be False
        fc = artifact.get("feature_contract") or {}
        if fc.get("name") != "NONE" or fc.get("dim") != 0:
            raise ValueError("v0 is NONE-only (F-A1b-AUDIT-1): feature_contract must be NONE/dim=0")
        if artifact.get("population_certified") is not False:
            raise ValueError("v0 invariant: population_certified must be False")
        q = int((artifact.get("admission") or {}).get("quality_code", _Q_NOMINAL))
        if q != _Q_NOMINAL:                            # NOMINAL-only writes (§6.3) — reject DEGRADED
            return None
        return self.store.append(artifact, _Q_NOMINAL, MATCH_PRESENCE)

    def status(self) -> dict:
        return {"enabled": self.cfg.enabled, "coherence_floor": self.cfg.coherence_floor,
                **self.store.status()}


def _cli() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="BCC Match — sealed gamer-local match-presence corpus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status", help="show BCC-match chain status (read-only)")
    st.add_argument("--out-dir", default=os.environ.get("BCC_MATCH_OUT_DIR", "bcc_match"))
    se = sub.add_parser("selftest", help="end-to-end demo in a temp lane (no real lane touched)")
    se.add_argument("--out-dir", default=None)
    a = ap.parse_args()

    if a.cmd == "status":
        print(json.dumps(MatchHarvester(BCCMatchConfig(out_dir=a.out_dir)).status(), indent=2))
        return 0

    if a.cmd == "selftest":
        import tempfile
        d = a.out_dir or tempfile.mkdtemp(prefix="bcc_match_selftest_")
        # a synthetic M17-shaped SYNCHRONIZED session (references only — no real capture)
        posp = {"verdict": "SYNCHRONIZED", "session_id": "demo_sid",
                "kas": {"commitment": "aa" * 32},
                "archive": {"dir": "retina_kf_archive/demo", "id_verified": True},
                "events_roots": {"kas_session_root": "bb" * 32, "retina_perception_root": None}}
        kas = {"verdict": "AUTHORED_SESSION", "commitment": "aa" * 32, "session_id": "demo_sid",
               "authored_kills": 8}
        artifact, reasons = build_match_presence_artifact(
            session_id="demo_sid", session_display="demo", posp=posp, kas=kas,
            authored_clusters=8, eligible_clusters=9, transport="RP")
        h = MatchHarvester(BCCMatchConfig(enabled=True, out_dir=d))
        rec = h.record(artifact)
        print(json.dumps({"lane": d, "built": artifact is not None, "reasons": reasons,
                          "recorded_seq": (rec or {}).get("seq"), **h.status()}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
