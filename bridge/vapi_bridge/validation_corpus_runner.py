"""
Phase 86 — Validation Corpus Runner.

Runs synthetic sessions through _rule_fallback and records results in the
synthetic_sessions table. Never touches ruling_validation_log — synthetic
sessions do NOT count toward the production consecutive_clean gate.

ISOLATION INVARIANT (W1 mitigation from Phase 86 WHAT_IF):
  A synthetic-only gate_passed would allow AGENT_DRY_RUN=false without any
  real human session validation. To prevent this:
  - Results go to synthetic_sessions table ONLY.
  - ruling_validation_log and consecutive_clean are never modified.
  - GET /agent/corpus-status includes isolation_note to document this clearly.
  - The production GET /agent/gate-readiness is unaffected by corpus runs.

Purpose:
1. Verify rule_fallback correctly classifies nominal synthetic evidence as CERTIFY
2. Exercise the corpus pipeline without real hardware
3. Provide regression test corpus — re-run after any rule_fallback code change;
   failed_fallback > 0 on a fresh nominal corpus = regression detected
"""

import logging
import time
import uuid

from .session_adjudicator import SessionAdjudicator
from .synthetic_session_generator import SyntheticSessionGenerator

log = logging.getLogger(__name__)


class ValidationCorpusRunner:
    """Runs synthetic sessions through rule_fallback.

    ISOLATION INVARIANT: Results stored in synthetic_sessions table ONLY.
    ruling_validation_log and consecutive_clean are never modified.
    """

    def __init__(self, cfg, store) -> None:
        self._cfg = cfg
        self._store = store
        self._n = int(getattr(cfg, "synthetic_corpus_size", 120))

    async def run_corpus(self, n: int | None = None) -> dict:
        """Run N synthetic sessions through rule_fallback.

        Returns:
            {generated, passed_fallback, failed_fallback, all_nominal,
             duration_ms, corpus_run_id, corpus_size}

        Never raises — errors are logged and reflected in failed_fallback count.
        """
        t0 = time.monotonic()
        corpus_size = n if n is not None else self._n
        corpus_run_id = uuid.uuid4().hex[:12]

        gen = SyntheticSessionGenerator()
        sessions = gen.generate_corpus(corpus_size)

        passed = 0
        failed = 0

        for sess in sessions:
            try:
                evidence = sess["evidence"]
                fb_verdict, fb_confidence, _ = SessionAdjudicator._rule_fallback(evidence)
                passed_fb = fb_verdict == "CERTIFY"
                if passed_fb:
                    passed += 1
                else:
                    failed += 1
                    log.warning(
                        "ValidationCorpusRunner: session %s got %s (expected CERTIFY) "
                        "— possible rule_fallback regression",
                        sess["session_id"], fb_verdict,
                    )
                self._store.insert_synthetic_session(
                    session_id=sess["session_id"],
                    device_id=sess["device_id"],
                    inference_code=sess["inference_code"],
                    humanity_score=sess["humanity_score"],
                    fallback_verdict=fb_verdict,
                    fallback_confidence=fb_confidence,
                    passed_fallback=int(passed_fb),
                    corpus_run_id=corpus_run_id,
                )
            except Exception as exc:
                failed += 1
                log.warning(
                    "ValidationCorpusRunner: session %s error: %s",
                    sess.get("session_id", "?"), exc,
                )

        duration_ms = round((time.monotonic() - t0) * 1000, 1)
        all_nominal = (passed == corpus_size) and corpus_size > 0

        log.info(
            "ValidationCorpusRunner: corpus_run_id=%s generated=%d "
            "passed=%d failed=%d (%.1fms)",
            corpus_run_id, corpus_size, passed, failed, duration_ms,
        )

        return {
            "generated": corpus_size,
            "passed_fallback": passed,
            "failed_fallback": failed,
            "all_nominal": all_nominal,
            "duration_ms": duration_ms,
            "corpus_run_id": corpus_run_id,
            "corpus_size": corpus_size,
        }
