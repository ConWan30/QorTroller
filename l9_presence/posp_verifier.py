"""PoSP record verifier — Arc A tournament-operator path.

Pure-function verification of a QORTROLLER-POSP-v0 record dict (from JSON).
No bridge, no chain, no IOTX. Reads only — designed for offline tournament-operator use.

Verification levels checked:
  STRUCTURAL   schema field matches "qortroller-posp-v0"; verdict is a known value;
               session_id is present and non-empty.
  COMMITMENT   kas.commitment is present and non-empty.
  CONSISTENCY  stored verdict matches the id_verified flags on kas + fusion surfaces
               (SYNCHRONIZED requires both; PARTIAL_SURFACES requires at least one).

On-disk archive SHA-256 cross-referencing and KAS file deep-verification are deferred
(gated on those files being co-located and CHAIN_SUBMISSION_PAUSED being lifted).
"""
from __future__ import annotations

from dataclasses import dataclass, field

EXPECTED_SCHEMA = "qortroller-posp-v0"
KNOWN_VERDICTS = frozenset({"SYNCHRONIZED", "PARTIAL_SURFACES", "UNVERIFIABLE"})

_CRITICAL = frozenset({"schema", "verdict_known", "session_id_present", "verdict_consistent"})


@dataclass(slots=True)
class CheckResult:
    name: str
    passed: bool
    note: str


@dataclass
class PoSPVerificationReport:
    schema_found: str | None
    verdict_found: str | None
    session_id: str | None
    checks: list = field(default_factory=list)
    overall: str = "UNVERIFIED"   # VERIFIED / PARTIAL / FAILED / SCHEMA_ERROR

    def passed(self) -> bool:
        return self.overall == "VERIFIED"


def verify_posp_record(record: dict) -> PoSPVerificationReport:
    """Verify a PoSP dict (loaded from JSON). Returns PoSPVerificationReport."""
    schema = record.get("schema")
    verdict = record.get("verdict")
    session_id = record.get("session_id")

    rep = PoSPVerificationReport(schema_found=schema, verdict_found=verdict,
                                  session_id=session_id)

    # S1: schema must match expected
    s1 = CheckResult("schema", schema == EXPECTED_SCHEMA,
                     f"expected {EXPECTED_SCHEMA!r}, got {schema!r}")
    rep.checks.append(s1)
    if not s1.passed:
        rep.overall = "SCHEMA_ERROR"
        return rep

    # S2: verdict must be a known closed-enum value
    s2 = CheckResult("verdict_known", verdict in KNOWN_VERDICTS,
                     f"verdict={verdict!r}, known={sorted(KNOWN_VERDICTS)}")
    rep.checks.append(s2)

    # S3: session_id (U1 join key) must be present
    s3 = CheckResult("session_id_present", bool(session_id),
                     "session_id present" if session_id else "session_id missing or null")
    rep.checks.append(s3)

    # S4a: KAS surface id_verified
    kas = record.get("kas") or {}
    kas_id_verified = bool(kas.get("id_verified", False))
    kas_commitment = kas.get("commitment") or ""
    s4a = CheckResult("kas_id_verified", kas_id_verified,
                      f"kas.id_verified={kas_id_verified!r}")
    rep.checks.append(s4a)

    # S4b: KAS commitment must be non-empty (the binding artifact)
    s4b = CheckResult("kas_commitment_present", bool(kas_commitment),
                      "kas.commitment present" if kas_commitment else "kas.commitment missing")
    rep.checks.append(s4b)

    # S5: fusion surface id_verified
    fusion = record.get("fusion") or {}
    fusion_id_verified = bool(fusion.get("id_verified", False))
    n_id = fusion.get("n_id_verified", 0)
    n_rows = fusion.get("n_rows", 0)
    s5 = CheckResult("fusion_id_verified", fusion_id_verified,
                     f"fusion.id_verified={fusion_id_verified!r}, "
                     f"n_id_verified={n_id}/{n_rows}")
    rep.checks.append(s5)

    # S6: verdict consistency
    if verdict == "SYNCHRONIZED":
        consistent = kas_id_verified and fusion_id_verified
        s6 = CheckResult("verdict_consistent", consistent,
                         "SYNCHRONIZED requires both kas.id_verified AND fusion.id_verified")
    elif verdict == "PARTIAL_SURFACES":
        consistent = kas_id_verified or fusion_id_verified
        s6 = CheckResult("verdict_consistent", consistent,
                         "PARTIAL_SURFACES requires at least one id-verified surface")
    else:
        s6 = CheckResult("verdict_consistent", True,
                         "UNVERIFIABLE: no consistency constraint to check")
    rep.checks.append(s6)

    # Determine overall result
    all_critical_pass = all(c.passed for c in rep.checks if c.name in _CRITICAL)
    if not all_critical_pass:
        rep.overall = "FAILED"
    elif verdict == "SYNCHRONIZED" and kas_id_verified and kas_commitment and fusion_id_verified:
        rep.overall = "VERIFIED"
    elif verdict == "PARTIAL_SURFACES" and (kas_id_verified or fusion_id_verified):
        rep.overall = "PARTIAL"
    else:
        rep.overall = "FAILED"

    return rep
