"""Phase O2-DRAFT-AUTOLOOP (Guardian) -- 2026-05-10.

Wires the three Guardian draft-generation primitives shipped in
operator_agent_guardian_drafting.py to a TESTABLE TRIGGER SURFACE.
Sibling of operator_agent_sentry_polling.py and the parallel-fleet
sibling of any future operator_agent_curator_polling.py.

SCAFFOLD-ONLY trigger sources via callback injection. The polling loop
DOES NOT subscribe to bus channels, watch directories, or query the
chain itself; it consumes from a `get_pending_triggers()` callback
that the operator wires up at boot. Follow-up phases ship the real
trigger producers (sweep_completed via cedar_drift_sweeper, fsca_finding
via fleet_signal_coherence_agent, commit via a git-watcher service).

CLASS SHAPE LOCKED across A/B/C polling agents -- symmetry matters.
Sentry's spec specifies the exact shape (operator_agent_sentry_polling
class GuardianPollingLoop sibling). DO NOT diverge.

TRIGGER DISPATCH MATRIX (per the brief):
  sweep_completed{sweep_id, findings_count, summary_text}
    -> draft_audit_entry(audit_id="sweep:{sweep_id}",
                         audit_payload={summary, findings_count},
                         audit_kind="sweep")
  fsca_finding{finding_id, severity, agents_involved, subject}
    -> draft_operational_diagnostic(diagnostic_id="fsca:{finding_id}",
                                    diagnostic_payload={subject, agents_involved},
                                    severity=severity)
  commit{commit_hash, repo, branch}
    -> draft_kms_sign(commit_hash, signer_pubkey_hex="",
                      signature_payload={repo, branch})
       AND
    -> draft_audit_entry(audit_id="commit:{commit_hash[:16]}",
                         audit_payload={event_type:"GIT_COMMIT",
                                        subject, repo, branch},
                         audit_kind="audit")

RATE LIMITING: ONE trigger per cycle (head of queue). Remaining
triggers wait for the next cycle. Prevents a flood of triggers from
overwhelming the store layer or the operator review surface in a
single tick.

FAIL-OPEN: any error inside a per-trigger handler is logged and
suppressed. The polling loop never raises out to the asyncio task
slot; only asyncio.CancelledError propagates (graceful shutdown).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, List, Optional

from .operator_agent_guardian_drafting import GuardianDraftGenerator

log = logging.getLogger(__name__)


# Default cadence; matches the cedar_drift_sweeper bundle interval
# floor (60s) but configurable via cfg.operator_agent_guardian_polling_interval_s.
_POLL_INTERVAL_DEFAULT_S = 30


GetPendingTriggersFn = Callable[[], List[dict]]


def _no_op_triggers() -> List[dict]:
    """Default trigger source -- returns empty list. Used by tests + by
    production deploys that have not yet wired up the real producers."""
    return []


class GuardianPollingLoop:
    """Phase O2-DRAFT-AUTOLOOP polling loop for Guardian.

    Class shape LOCKED -- see module docstring. Sentry/Curator siblings
    must mirror constructor signature, start(), stop(), and
    _drafts_this_session().
    """

    def __init__(
        self,
        *,
        cfg: Any,
        store: Any,
        draft_generator: GuardianDraftGenerator,
        get_pending_triggers: GetPendingTriggersFn,
    ) -> None:
        self._cfg = cfg
        self._store = store
        self._gen = draft_generator
        self._get_pending = get_pending_triggers
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._drafts_count = 0
        self._interval_s = int(
            getattr(cfg, "operator_agent_guardian_polling_interval_s",
                    _POLL_INTERVAL_DEFAULT_S)
        )

    def _drafts_this_session(self) -> int:
        """Number of drafts produced since this loop instance started."""
        return self._drafts_count

    async def start(self) -> None:
        """Start the polling loop as an asyncio task. Idempotent: if a
        task is already running, this is a no-op."""
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        # Best-effort name (3.8+).
        try:
            self._task.set_name("GuardianPollingLoop._run")
        except AttributeError:
            pass

    async def stop(self) -> None:
        """Signal the loop to exit and await task completion. Safe to
        call multiple times."""
        self._stop_event.set()
        if self._task is None:
            return
        if self._task.done():
            self._task = None
            return
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 -- shutdown must not raise
            log.warning("GuardianPollingLoop.stop: task await error: %s", exc)
        finally:
            self._task = None

    async def _run(self) -> None:
        """Inner async loop. Wakes every interval_s seconds, pulls
        triggers, dispatches HEAD ONE per cycle. Fail-open."""
        log.info(
            "GuardianPollingLoop: started interval=%ds", self._interval_s
        )
        while not self._stop_event.is_set():
            try:
                triggers = self._safe_get_triggers()
                if triggers:
                    head = triggers[0]
                    self._dispatch_one(head)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 -- loop must not die
                log.exception(
                    "GuardianPollingLoop: outer loop error: %s", exc
                )

            # Sleep with stop-event wake-up so stop() returns promptly.
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._interval_s
                )
            except asyncio.TimeoutError:
                pass
        log.info("GuardianPollingLoop: stopped")

    def _safe_get_triggers(self) -> List[dict]:
        try:
            res = self._get_pending() or []
        except Exception as exc:  # noqa: BLE001 -- fail-open
            log.warning(
                "GuardianPollingLoop: get_pending_triggers error: %s", exc
            )
            return []
        if not isinstance(res, list):
            log.warning(
                "GuardianPollingLoop: get_pending_triggers returned %s; "
                "expected list",
                type(res).__name__,
            )
            return []
        return res

    def _dispatch_one(self, trigger: dict) -> None:
        """Dispatch a single trigger to the matching draft method(s).
        Errors are caught + logged; never re-raised."""
        if not isinstance(trigger, dict):
            log.warning(
                "GuardianPollingLoop: trigger is %s, not dict; skipping",
                type(trigger).__name__,
            )
            return
        kind = trigger.get("kind")
        payload = trigger.get("payload") or {}
        if not isinstance(payload, dict):
            log.warning(
                "GuardianPollingLoop: trigger payload is %s, not dict; "
                "kind=%r",
                type(payload).__name__, kind,
            )
            return

        try:
            if kind == "sweep_completed":
                self._handle_sweep_completed(payload)
            elif kind == "fsca_finding":
                self._handle_fsca_finding(payload)
            elif kind == "commit":
                self._handle_commit(payload)
            else:
                log.warning(
                    "GuardianPollingLoop: unknown trigger kind=%r", kind
                )
        except Exception as exc:  # noqa: BLE001 -- fail-open per-trigger
            log.warning(
                "GuardianPollingLoop: handler error kind=%r: %s",
                kind, exc,
            )

    # ------------------------------------------------------------------
    # Trigger handlers
    # ------------------------------------------------------------------
    def _handle_sweep_completed(self, payload: dict) -> None:
        sweep_id = str(payload.get("sweep_id", "")).strip()
        if not sweep_id:
            log.warning(
                "GuardianPollingLoop: sweep_completed missing sweep_id"
            )
            return
        findings_count = int(payload.get("findings_count", 0) or 0)
        summary_text = str(payload.get("summary_text", ""))

        result = self._gen.draft_audit_entry(
            audit_id=f"sweep:{sweep_id}",
            audit_payload={
                "summary": summary_text,
                "findings_count": findings_count,
            },
            audit_kind="sweep",
        )
        self._record_result(result, "sweep_completed")

    def _handle_fsca_finding(self, payload: dict) -> None:
        finding_id = str(payload.get("finding_id", "")).strip()
        if not finding_id:
            log.warning(
                "GuardianPollingLoop: fsca_finding missing finding_id"
            )
            return
        severity = str(payload.get("severity", "info")).strip() or "info"
        agents_involved = payload.get("agents_involved") or []
        if not isinstance(agents_involved, list):
            agents_involved = []
        subject = str(payload.get("subject", ""))

        result = self._gen.draft_operational_diagnostic(
            diagnostic_id=f"fsca:{finding_id}",
            diagnostic_payload={
                "subject": subject,
                "agents_involved": list(agents_involved),
            },
            severity=severity,
        )
        self._record_result(result, "fsca_finding")

    def _handle_commit(self, payload: dict) -> None:
        commit_hash = str(payload.get("commit_hash", "")).strip()
        if not commit_hash:
            log.warning(
                "GuardianPollingLoop: commit missing commit_hash"
            )
            return
        repo = str(payload.get("repo", ""))
        branch = str(payload.get("branch", ""))

        # 1) kms-sign on the commit hash
        sig_result = self._gen.draft_kms_sign(
            commit_hash=commit_hash,
            signer_pubkey_hex="",
            signature_payload={"repo": repo, "branch": branch},
        )
        self._record_result(sig_result, "commit/kms-sign")

        # 2) audit-entry capturing the GIT_COMMIT event
        # commit_hash[:16] truncation matches the brief's matrix.
        audit_result = self._gen.draft_audit_entry(
            audit_id=f"commit:{commit_hash[:16]}",
            audit_payload={
                "event_type": "GIT_COMMIT",
                "subject": commit_hash,
                "repo": repo,
                "branch": branch,
            },
            audit_kind="audit",
        )
        self._record_result(audit_result, "commit/audit")

    def _record_result(self, result: Any, label: str) -> None:
        """Increment in-session counter on successful draft persistence."""
        try:
            err = getattr(result, "error", None)
            draft_id = int(getattr(result, "draft_id", 0) or 0)
        except Exception:  # noqa: BLE001
            err = "result-introspect-error"
            draft_id = 0
        if err:
            log.info(
                "GuardianPollingLoop: %s draft error=%s", label, err
            )
            return
        if draft_id <= 0:
            return
        self._drafts_count += 1
        log.debug(
            "GuardianPollingLoop: %s draft persisted id=%d total=%d",
            label, draft_id, self._drafts_count,
        )


async def run_guardian_polling_loop(
    *,
    cfg: Any,
    store: Any,
    draft_generator: Optional[GuardianDraftGenerator] = None,
    get_pending_triggers: Optional[GetPendingTriggersFn] = None,
) -> None:
    """Module-level entrypoint for main.py task wiring.

    Short-circuits when cfg.operator_agent_guardian_polling_enabled is
    False (opt-in default).

    Constructs a GuardianDraftGenerator if draft_generator is None.
    Uses _no_op_triggers if get_pending_triggers is None (the
    polling loop will simply idle until the operator wires up real
    triggers in a follow-up phase).
    """
    if not getattr(cfg, "operator_agent_guardian_polling_enabled", False):
        log.info(
            "GuardianPollingLoop: disabled "
            "(operator_agent_guardian_polling_enabled=False)"
        )
        return

    gen = draft_generator
    if gen is None:
        gen = GuardianDraftGenerator(cfg=cfg, store=store)

    triggers_fn = get_pending_triggers or _no_op_triggers

    loop = GuardianPollingLoop(
        cfg=cfg,
        store=store,
        draft_generator=gen,
        get_pending_triggers=triggers_fn,
    )
    await loop.start()
    # Block until cancelled (matches cedar_drift_sweeper.run_drift_sweep_loop
    # contract: returns only on graceful shutdown).
    try:
        if loop._task is not None:
            await loop._task
    except asyncio.CancelledError:
        await loop.stop()
        raise
