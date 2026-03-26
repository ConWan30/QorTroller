"""
Phase 86 — Synthetic Session Generator.

Generates synthetic nominal device sessions for validation corpus runs.

ISOLATION INVARIANT: Synthetic sessions NEVER enter ruling_validation_log and
NEVER count toward the production consecutive_clean gate. They are stored only
in the synthetic_sessions table, tagged device_id="synthetic_<hex>" for clarity.

Purpose:
1. Verify rule_fallback correctly classifies nominal evidence as CERTIFY
2. Exercise the pipeline end-to-end without requiring real hardware
3. Provide a deterministic regression corpus — re-run after any rule_fallback
   change; a verdict delta flags the regression (Phase 87 candidate)
"""

import json
import random
import time
import uuid

_NOMINAL_INFERENCE_CODE = 0x20  # NOMINAL — no advisory or hard codes


def _make_nominal_evidence(rng: random.Random) -> dict:
    """Return an evidence dict that _rule_fallback scores as CERTIFY.

    rule_fallback priority (from session_adjudicator.py):
      1. hard_cheat_codes present → BLOCK (we set [])
      2. enrollment_status == "eligible" → CERTIFY  ← we hit this path
      3. risk_label == "critical" → HOLD
      4. advisory_codes present → FLAG
      5. default → FLAG (0.05)

    So: empty hard_cheat_codes + enrollment_status="eligible" → CERTIFY (0.8).
    """
    return {
        "enrollment_status": "eligible",
        "nominal_sessions": rng.randint(15, 60),
        "hard_cheat_codes": [],
        "advisory_codes": [],
        "risk_label": "nominal",
        "humanity_score": round(rng.uniform(0.65, 0.92), 3),
        "inference_code": _NOMINAL_INFERENCE_CODE,
        "l4_mahalanobis_anomaly": round(rng.uniform(1.5, 5.0), 3),
        "l4_mahalanobis_continuity": round(rng.uniform(1.2, 4.2), 3),
        "l5_cv": round(rng.uniform(0.01, 0.07), 4),
        "l5_entropy": round(rng.uniform(1.2, 2.8), 3),
        "source": "synthetic_corpus",
    }


class SyntheticSessionGenerator:
    """Generate synthetic nominal device sessions for corpus validation.

    Each session:
    - device_id: "synthetic_<12-hex>" — clearly identified as synthetic
    - evidence: enrollment_status="eligible" → rule_fallback → CERTIFY, 0.8
    - humanity_score: 0.65–0.92 (nominal human range)
    - inference_code: 0x20 (NOMINAL)

    All biometric feature values are within L4 calibration thresholds
    (anomaly < 7.009, continuity < 5.367) by construction.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def generate_session(self) -> dict:
        """Generate one synthetic nominal session dict."""
        session_id = f"synthetic_{uuid.UUID(int=self._rng.getrandbits(128)).hex[:16]}"
        device_id = f"synthetic_{uuid.UUID(int=self._rng.getrandbits(128)).hex[:12]}"
        evidence = _make_nominal_evidence(self._rng)
        return {
            "session_id": session_id,
            "device_id": device_id,
            "inference_code": _NOMINAL_INFERENCE_CODE,
            "humanity_score": evidence["humanity_score"],
            "evidence": evidence,
            "evidence_json": json.dumps(evidence),
            "created_at": time.time(),
        }

    def generate_corpus(self, n: int = 10) -> list:
        """Generate N synthetic nominal sessions. Returns list of session dicts."""
        return [self.generate_session() for _ in range(n)]
