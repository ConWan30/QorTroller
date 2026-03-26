"""Phase 107 — Live Mode Readiness Validator.

Runs N synthetic NOMINAL sessions through SessionAdjudicator._rule_fallback().
A BLOCK on a nominal session = false positive.

ready_for_live = n_tested >= 100 AND false_positive_count == 0 AND
                 activation_committed AND NOT dry_run_active AND pmi >= 1

W1 isolation: results go to live_mode_readiness_reports table only.
Never touches ruling_validation_log (gate). Never raises from run_validation().
"""
import time
import logging

log = logging.getLogger(__name__)


class LiveModeReadinessValidator:

    def __init__(self, cfg, store) -> None:
        self._cfg   = cfg
        self._store = store

    async def run_validation(self, n: int = 100) -> dict:
        """Run n nominal sessions through rule_fallback. Returns report dict."""
        t0 = time.time()
        result = {
            "n_tested": 0, "false_positive_count": 0, "false_positive_rate": 0.0,
            "activation_committed": False, "pmi": 0, "dry_run_active": True,
            "ready_for_live": False, "notes": "", "error": None,
        }
        try:
            state          = self._store.get_activation_state()
            pmi            = self._store.compute_pmi()
            dry_run_active = bool(getattr(self._cfg, "agent_dry_run_mode", True))
            committed      = state.get("activation_committed", False)
            result.update({"activation_committed": committed, "pmi": pmi,
                           "dry_run_active": dry_run_active})

            from .synthetic_session_generator import SyntheticSessionGenerator
            from .session_adjudicator import SessionAdjudicator
            corpus = SyntheticSessionGenerator(seed=107).generate_corpus(n)

            false_positives = 0
            for session in corpus:
                try:
                    verdict, _, _ = SessionAdjudicator._rule_fallback(session["evidence"])
                    if verdict == "BLOCK":
                        false_positives += 1
                except Exception as exc:
                    log.debug("readiness _rule_fallback failed: %s", exc)
                    false_positives += 1  # conservative

            n_tested = len(corpus)
            fp_rate  = round(false_positives / n_tested, 4) if n_tested > 0 else 0.0
            ready    = (n_tested >= 100 and false_positives == 0
                        and committed and not dry_run_active and pmi >= 1)

            result.update({
                "n_tested": n_tested, "false_positive_count": false_positives,
                "false_positive_rate": fp_rate, "ready_for_live": ready,
                "duration_ms": round((time.time() - t0) * 1000, 1),
            })
            self._store.insert_readiness_report(
                n_tested=n_tested, false_positive_count=false_positives,
                false_positive_rate=fp_rate,
                activation_committed=1 if committed else 0, pmi=pmi,
                dry_run_active=1 if dry_run_active else 0,
                ready_for_live=1 if ready else 0,
                notes=f"phase107_validation n={n}",
            )
        except Exception as exc:
            result["error"] = str(exc)
            log.warning("LiveModeReadinessValidator: run_validation failed: %s", exc)
        return result
