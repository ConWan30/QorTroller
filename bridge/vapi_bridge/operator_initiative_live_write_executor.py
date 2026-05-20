"""Phase O1-D-PATH-B v1 — Per-agent Live-Write Authorization + Executor.

Closes the second gate the O3 ceremony exposed: cryptographic Cedar
authority (O3_ACTING bundles anchored on-chain) granted live-write
permission, but the bridge had no executor consuming `operator_decision=
'accept'` drafts and firing the corresponding chain operations. This
module provides the AUTHORIZATION primitive + the EXECUTOR.

═════════════════════════════════════════════════════════════════════════
Design — three-gate safety contract
═════════════════════════════════════════════════════════════════════════

For an agent's chain operation to fire autonomously, ALL of:

  1. agent at O3_ACTING phase (verified via operator_agent_activation_log)
  2. cfg.phase_o3_{agent}_live_writes_enabled == True (per-agent opt-in)
  3. daily spending under cfg.phase_o3_{agent}_daily_iotx_budget
  4. cfg.phase_o3_executor_kill_all == False (emergency halt)

PLUS the existing chain-layer kill-switch (cfg.chain_submission_paused)
remains enforced at chain.py:_send_tx. This module's check above is
a PRE-EXECUTION gate; the chain layer is the FINAL gate. Both must
align for execution to actually fire.

Default posture:
  - phase_o3_{agent}_live_writes_enabled = False (conservative; OPT-IN)
  - phase_o3_{agent}_daily_iotx_budget   = 0.5 (chain agents)
                                         = 0.0 (Guardian; no chain ops)
  - phase_o3_executor_kill_all           = False (executor allowed to run
                                          if other gates pass)

═════════════════════════════════════════════════════════════════════════
Audit-trail discipline
═════════════════════════════════════════════════════════════════════════

Every chain operation fired by the executor is logged to
operator_agent_chain_spending_log with (agent_id, draft_id, action_name,
cost_iotx, tx_hash, fired_at, error). Budget enforcement aggregates
cost_iotx for the current UTC day per agent. Refusal events (gate
failures, budget exhaustion, kill-all activated) are ALSO logged with
cost_iotx=0 + error populated so the audit trail captures both
"executed" and "refused" decisions.

This pairs cleanly with the supersession primitive's design:
attestation rows in operator_initiative_auto_supersede_log document
WHY each agent reached O3_ACTING; spending rows in
operator_agent_chain_spending_log document WHAT each agent did once
authorized.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


# Per-agent budget defaults (IOTX per day; 0.0 = no chain ops permitted)
DEFAULT_BUDGET_IOTX_BY_AGENT = {
    "anchor_sentry": 0.5,  # PoAd anchoring at ~0.0008/anchor = ~625 anchors/day budget
    "guardian":      0.0,  # No chain ops; Guardian's O3 authority is local writes only
    "curator":       0.5,  # marketplace-suspend at ~0.001/op = ~500 suspensions/day budget
}


@dataclass(frozen=True, slots=True)
class LiveWriteAuthorization:
    """Result of evaluating whether an agent may fire a chain operation.

    `authorized=True` means all gates passed. `blockers` lists which
    gates failed (empty if authorized). `budget_remaining_iotx` reports
    how much budget the agent has left today.
    """

    agent_id: str
    authorized: bool
    blockers: tuple[str, ...]
    budget_remaining_iotx: float
    daily_budget_iotx: float
    daily_spent_iotx: float
    error: Optional[str] = None


def _get_agent_budget(cfg, agent_id: str) -> float:
    """Read per-agent daily IOTX budget from cfg, with default fallback."""
    key = f"phase_o3_{agent_id}_daily_iotx_budget"
    val = getattr(cfg, key, None)
    if val is not None:
        return float(val)
    return float(DEFAULT_BUDGET_IOTX_BY_AGENT.get(agent_id, 0.0))


def _agent_live_writes_enabled(cfg, agent_id: str) -> bool:
    """Read per-agent live-writes flag (default False)."""
    return bool(getattr(cfg, f"phase_o3_{agent_id}_live_writes_enabled", False))


def evaluate_live_write_authorization_for_agent(
    *,
    agent_id: str,
    cfg,
    store,
    intended_cost_iotx: float = 0.0,
) -> LiveWriteAuthorization:
    """Per-agent four-gate evaluation.

    `intended_cost_iotx` is the projected cost of the next operation
    (caller estimates via gas × price + safety buffer). The authorization
    checks if `daily_spent + intended_cost <= daily_budget`. If
    intended_cost=0, the check is "any budget remaining" only.

    Never raises — returns LiveWriteAuthorization with error populated
    on any exception.
    """
    blockers: list[str] = []
    daily_spent = 0.0
    daily_budget = _get_agent_budget(cfg, agent_id)

    try:
        # Gate 4 (emergency): cfg.phase_o3_executor_kill_all
        if bool(getattr(cfg, "phase_o3_executor_kill_all", False)):
            blockers.append("phase_o3_executor_kill_all_active")

        # Gate 2: per-agent live-writes flag
        if not _agent_live_writes_enabled(cfg, agent_id):
            blockers.append(f"phase_o3_{agent_id}_live_writes_disabled")

        # Resolve canonical agent_id → Q9 hex once (used by both gates 1 + 3).
        agent_q9 = str(
            getattr(cfg, f"operator_agent_{agent_id}_id", "") or ""
        ).lower()

        # Gate 1: agent phase must be O3_ACTING (consult activation_log via
        # store helper). We tolerate the helper being absent — fail-open
        # to "phase unknown" blocker.
        try:
            if agent_q9:
                rows = store.get_operator_agent_activation_log(agent_q9, limit=1)
                latest = rows[0] if rows else None
                to_phase = str((latest or {}).get("to_phase", "") or "").upper()
                if to_phase != "O3_ACTING" and to_phase != "O3_ACT":
                    blockers.append(f"phase_is_{to_phase or 'unknown'}_not_O3_ACTING")
            else:
                blockers.append(f"operator_agent_{agent_id}_id_not_configured")
        except Exception as exc:
            blockers.append(f"activation_log_read_failed_{type(exc).__name__}")

        # Gate 3: daily budget — query by Q9 hex (the actual key used by
        # insert_chain_spending_event callers; both executor + tests).
        try:
            lookup_key = agent_q9 if agent_q9 else agent_id
            daily_spent = float(store.get_daily_chain_spending_for_agent(lookup_key) or 0.0)
        except Exception:
            daily_spent = 0.0  # fail-open to 0 spent; budget check still runs

        projected = daily_spent + max(0.0, float(intended_cost_iotx))
        # Gap 1 closure 2026-05-19: budget=0.0 means "no IOTX budget"; if the
        # intended op also costs nothing (e.g., Guardian's audit-drafting
        # writes locally — no chain dependency, no IOTX cost), permit it.
        # Per L38 PATH-B v1 NOTE: "Guardian 0.0 by default (its O3 authority
        # is local writes — no chain dependency, no budget needed)."
        if daily_budget <= 0.0:
            if float(intended_cost_iotx) > 0.0:
                # Chain ops require positive budget; this is the original block.
                blockers.append(f"daily_budget_zero_no_chain_ops_permitted")
            # else: budget=0 + cost=0 = local-only action; permit (no blocker added).
        elif projected > daily_budget:
            blockers.append(
                f"daily_budget_exceeded_spent_{daily_spent:.6f}"
                f"_plus_projected_{intended_cost_iotx:.6f}_over_{daily_budget:.6f}"
            )

        authorized = len(blockers) == 0
        budget_remaining = max(0.0, daily_budget - daily_spent)
        return LiveWriteAuthorization(
            agent_id=agent_id,
            authorized=authorized,
            blockers=tuple(blockers),
            budget_remaining_iotx=budget_remaining,
            daily_budget_iotx=daily_budget,
            daily_spent_iotx=daily_spent,
        )
    except Exception as exc:
        return LiveWriteAuthorization(
            agent_id=agent_id,
            authorized=False,
            blockers=("evaluation_error",),
            budget_remaining_iotx=0.0,
            daily_budget_iotx=daily_budget,
            daily_spent_iotx=daily_spent,
            error=f"{type(exc).__name__}: {exc}",
        )


class OperatorAgentLiveWriteExecutor:
    """Async loop that processes accepted drafts → chain operations.

    Runs alongside the existing polling loops. On each cycle, for each
    enabled agent, reads new operator_decision='accept' drafts not yet
    executed + fires the corresponding chain operation + logs spending.

    Default cadence: 60 seconds (slower than draft generators to keep
    executor load light). Configurable via cfg.phase_o3_executor_interval_s.

    SAFETY MODEL: this class only fires chain operations when
    evaluate_live_write_authorization_for_agent returns authorized=True
    for the agent. With default cfg (all live_writes_enabled flags False),
    the executor STRUCTURALLY NO-OPS — every cycle returns "0 drafts
    processed" because every agent's authorization fails the per-agent
    flag gate.

    The executor never raises. Per-draft errors are logged + recorded
    in the spending log with cost_iotx=0 + error populated. The loop
    continues on errors per the fail-open contract.
    """

    def __init__(
        self,
        *,
        cfg,
        store,
        chain,
        interval_s: int = 60,
    ) -> None:
        self.cfg = cfg
        self.store = store
        self.chain = chain
        self.interval_s = max(10, int(interval_s))
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        """Main loop. Yields to event loop between cycles.

        Per the Phase 235.x-STABILITY arc, this loop MUST NOT block the
        event loop with sync DB work. All store reads are sync but
        bounded; chain calls are async + already use to_thread internally
        via chain.py's existing pattern.
        """
        log.info(
            "Phase O1-D-PATH-B: live-write executor started (interval=%ds)",
            self.interval_s,
        )
        try:
            while not self._stop.is_set():
                try:
                    await self._process_cycle()
                except Exception as exc:
                    log.warning("live-write executor cycle failed: %s", exc)
                # Wait for the next cycle or stop signal, whichever comes first
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.interval_s
                    )
                    break  # stop signal received
                except asyncio.TimeoutError:
                    continue  # normal cycle interval elapsed
        except asyncio.CancelledError:
            log.info("Phase O1-D-PATH-B: live-write executor cancelled")
            raise

    async def _process_cycle(self) -> None:
        """One executor cycle: per-agent gate check + accepted-draft processing.

        Phase 235.x-STABILITY-8 2026-05-17: sync DB work (authorization
        eval + draft fetch) wrapped in asyncio.to_thread to prevent SQL
        queries from blocking the event loop. The 6 sync store calls in
        the original implementation were a Phase 235.x-STABILITY-2
        pattern violation that compounded with 4 MLGA trackers + 40+
        other background tasks to cause sustained loop_starvation events
        (6-25s) and bridge zombies.
        """
        for agent_id in ("anchor_sentry", "guardian", "curator"):
            try:
                # All per-agent sync DB work bundled into one to_thread
                # call so the event loop is yielded between agents.
                agent_q9, auth, drafts = await asyncio.to_thread(
                    self._gather_per_agent_state_sync, agent_id,
                )
                if not auth.authorized or not agent_q9:
                    # Silent skip is correct: per-agent live_writes_enabled=False
                    # (most common case); no spending row written.
                    continue
                for draft in drafts or []:
                    await self._execute_draft(agent_id, agent_q9, draft)
            except Exception as exc:
                log.warning(
                    "live-write executor: per-agent loop failed for %s: %s",
                    agent_id, exc,
                )

    def _gather_per_agent_state_sync(self, agent_id: str):
        """Sync helper — runs in worker thread via asyncio.to_thread.
        Returns (agent_q9, auth, drafts). Empty drafts list on any failure."""
        auth = evaluate_live_write_authorization_for_agent(
            agent_id=agent_id, cfg=self.cfg, store=self.store,
            intended_cost_iotx=0.0,
        )
        if not auth.authorized:
            return None, auth, []
        agent_q9 = str(
            getattr(self.cfg, f"operator_agent_{agent_id}_id", "") or ""
        ).lower()
        if not agent_q9:
            return None, auth, []
        try:
            drafts = self.store.get_accepted_unexecuted_drafts(agent_q9, limit=5)
        except Exception as exc:
            log.warning(
                "live-write executor: get_drafts failed for %s: %s",
                agent_id, exc,
            )
            drafts = []
        return agent_q9, auth, (drafts or [])

    async def _execute_draft(
        self, agent_id: str, agent_q9: str, draft: dict,
    ) -> None:
        """Fire ONE accepted draft as a real chain operation.

        Implementation note: the actual chain.py call signature varies per
        action_name. For Path B v1 ship, we route a small set of known
        action_names (pda-attestation-anchor + marketplace-listing-suspend);
        unknown actions are logged + recorded as "no_executor_for_action"
        in the spending log. Path B v2 extends the routing as more
        action_names need autonomous execution.
        """
        draft_id = int(draft.get("id", 0) or 0)
        action_name = str(draft.get("action_name", "") or "")
        intended_cost = self._estimate_cost_iotx(action_name)

        # Per-call authorization (re-check with intended_cost for budget).
        # Phase 235.x-STABILITY-8 2026-05-17: wrap sync DB read in
        # to_thread (lambda needed because evaluate_* takes keyword-only).
        auth = await asyncio.to_thread(
            lambda: evaluate_live_write_authorization_for_agent(
                agent_id=agent_id, cfg=self.cfg, store=self.store,
                intended_cost_iotx=intended_cost,
            )
        )
        if not auth.authorized:
            await asyncio.to_thread(
                self._record_refusal, agent_q9, draft_id, action_name, auth.blockers,
            )
            # Refusal-churn cap (2026-05-20): if the refusal is structurally
            # permanent (no executor route, or a chain-cost action under a
            # budget=0 agent), mark the draft refused so it drops out of the
            # next fetch instead of being re-evaluated + re-logged every cycle.
            if self._is_terminal_refusal(auth.blockers):
                await asyncio.to_thread(
                    self.store.mark_draft_refused, draft_id,
                    "; ".join(auth.blockers) if auth.blockers else "terminal_refusal",
                )
            return

        # Route by action_name. v1 set is minimal — extend in v2.
        # Gap 1 closure 2026-05-19: route audit-drafting through Guardian's
        # local handler (no chain dependency, synthetic local: tx_hash for
        # spending_log audit trail distinction).
        try:
            if action_name == "pda-attestation-anchor":
                tx_hash, cost_iotx = await self._exec_sentry_pda_anchor(draft)
            elif action_name == "marketplace-listing-suspend":
                tx_hash, cost_iotx = await self._exec_curator_listing_suspend(draft)
            elif action_name == "audit-drafting":
                tx_hash, cost_iotx = await self._exec_guardian_audit_draft(draft)
            elif action_name == "operational-diagnostic":
                tx_hash, cost_iotx = await self._exec_guardian_operational_diagnostic(draft)
            else:
                # No executor routed for this action_name — structurally
                # permanent, so record ONCE and mark refused (drops out of the
                # next fetch; no per-cycle re-logging). Phase 235.x-STABILITY-8:
                # sync DB writes wrapped in to_thread.
                _reason = f"no_executor_for_action_{action_name}"
                await asyncio.to_thread(
                    self._record_refusal, agent_q9, draft_id, action_name, (_reason,),
                )
                await asyncio.to_thread(
                    self.store.mark_draft_refused, draft_id, _reason,
                )
                return
        except Exception as exc:
            log.warning(
                "live-write executor: action %s failed for draft id=%d: %s",
                action_name, draft_id, exc,
            )
            await asyncio.to_thread(
                self._record_refusal, agent_q9, draft_id, action_name,
                (f"chain_call_failed_{type(exc).__name__}",),
            )
            return

        # Record successful execution. Phase 235.x-STABILITY-8: sync
        # DB writes wrapped in to_thread.
        try:
            await asyncio.to_thread(
                lambda: self.store.insert_chain_spending_event(
                    agent_id=agent_q9, draft_id=draft_id, action_name=action_name,
                    cost_iotx=float(cost_iotx), tx_hash=str(tx_hash or ""),
                    error=None,
                )
            )
            await asyncio.to_thread(
                self.store.mark_draft_executed, draft_id, str(tx_hash or ""),
            )
            log.info(
                "Phase O1-D-PATH-B: agent=%s draft=%d action=%s tx=%s cost=%.6f IOTX",
                agent_id, draft_id, action_name,
                (tx_hash[:18] if tx_hash else ""), cost_iotx,
            )
        except Exception as exc:
            log.warning("live-write executor: post-exec persistence failed: %s", exc)

    def _record_refusal(
        self, agent_q9: str, draft_id: int, action_name: str,
        blockers: tuple[str, ...],
    ) -> None:
        """Record a refusal/skip event in spending log (cost_iotx=0)."""
        try:
            self.store.insert_chain_spending_event(
                agent_id=agent_q9, draft_id=draft_id, action_name=action_name,
                cost_iotx=0.0, tx_hash="",
                error="; ".join(blockers) if blockers else "unknown_refusal",
            )
        except Exception:
            pass  # fail-open: idempotent spending log writes

    @staticmethod
    def _is_terminal_refusal(blockers) -> bool:
        """True when a refusal is structurally permanent under current routing/
        config and will recur identically every cycle — so the draft should be
        marked refused (dropped from the fetch) rather than re-attempted +
        re-logged forever. Transient blockers (RPC failure, daily-budget-
        exceeded which resets at midnight) are NOT terminal and should retry."""
        for b in (blockers or ()):
            b = str(b)
            if b.startswith("no_executor_for_action"):
                return True
            if b == "daily_budget_zero_no_chain_ops_permitted":
                # Permanent for a budget=0 (local-only) agent: a chain-cost
                # action will never be permitted without a config change.
                return True
        return False

    @staticmethod
    def _estimate_cost_iotx(action_name: str) -> float:
        """Conservative per-action cost estimate for budget pre-check.

        Real cost varies with network gas; this is the safety-margin
        estimate used to refuse drafts that would push agents over budget.
        Underestimates here would let drafts through that then exceed
        budget at submit time; overestimates cost throughput but is safer.
        """
        return {
            "pda-attestation-anchor":      0.001,   # PoAd anchor ~0.0008 typical
            "marketplace-listing-suspend": 0.002,   # suspension ~0.001 typical
            # Guardian's O3 authority is LOCAL writes (lane://audits/** +
            # lane://ops/**); no chain dependency, zero IOTX cost. Both
            # audit-drafting (Gap 1 closure 2026-05-19) AND operational-
            # diagnostic (2026-05-20: was falling to the default 0.001 and
            # getting refused at Guardian's budget=0 as daily_budget_zero_
            # no_chain_ops_permitted — 7k+ refusal rows). Both are local.
            "audit-drafting":              0.0,
            "operational-diagnostic":      0.0,
            # Guardian's kms-sign on draft://commit_hashes/* IS Cedar-permitted
            # (all 4 Guardian bundles) — it signs a commit hash locally, no
            # chain submission, zero IOTX. Zero-costed so it is NOT mislabeled
            # as a budget refusal; it currently has NO executor route (no fake
            # signer — that would falsely claim a signature), so it resolves to
            # an honest no_executor_for_action_kms-sign terminal refusal until a
            # real Guardian signing executor is deliberately wired.
            "kms-sign":                    0.0,
        }.get(action_name, 0.001)

    async def _exec_sentry_pda_anchor(self, draft: dict) -> tuple[str, float]:
        """Sentry's pda-attestation-anchor: call chain.record_adjudication.

        Returns (tx_hash, cost_iotx).
        """
        # Extract payload from draft. The draft was constructed by
        # operator_agent_sentry_drafting.draft_pda_anchor() with a payload
        # dict containing device_id_hash_hex + poad_hash_hex + dual_veto.
        import json as _json
        try:
            payload = _json.loads(str(draft.get("payload_bytes_decoded", "{}")) or "{}")
        except Exception:
            payload = {}
        device_id_hash = str(payload.get("device_id_hash_hex", "") or "")
        poad_hash = str(payload.get("poad_hash_hex", "") or "")
        dual_veto = bool(payload.get("dual_veto", False))
        if not device_id_hash or not poad_hash:
            raise ValueError("pda-anchor draft payload missing device_id_hash or poad_hash")
        # Defer to chain.record_adjudication (already async + handles kill-switch
        # + uses gas estimation).
        result = await self.chain.record_adjudication(
            device_id_hash=device_id_hash, poad_hash=poad_hash, dual_veto=dual_veto,
        )
        tx_hash = str(result.get("tx_hash", "") or "")
        cost_iotx = float(result.get("cost_iotx", 0.0) or 0.0)
        return tx_hash, cost_iotx

    async def _exec_guardian_audit_draft(self, draft: dict) -> tuple[str, float]:
        """Guardian's audit-drafting: LOCAL write (no chain dependency).

        Gap 1 closure 2026-05-19. Per L38 PATH-B v1 NOTE: "Guardian's O3
        authority is `audit-drafting` on `lane://audits/**` (live writes
        to audit trail)" — these writes do NOT touch chain. The synthetic
        tx_hash format `local:audit:<draft_id>` distinguishes local audit
        writes from chain operations in the spending_log audit trail.

        The actual audit content lives in operator_agent_drafts.payload_*;
        marking the draft as executed records its execution. Future
        extension can write structured audit rows to a dedicated audit
        table (lane://audits/**), but for the MVP closure, the spending
        log row + the drafts table executed_at marker provide the audit
        trail.

        Returns (synthetic_local_tx_hash, 0.0).
        """
        draft_id = int(draft.get("id", 0) or 0)
        # Synthetic local: tx_hash for audit trail distinction in spending_log.
        # mythos_spending_log_drift's UNATTRIBUTED_CHAIN_TX check fires only on
        # cost > 0 with empty tx_hash; cost=0 + local: prefix is fine.
        synthetic_tx_hash = f"local:audit:{draft_id}"
        cost_iotx = 0.0
        return synthetic_tx_hash, cost_iotx

    async def _exec_guardian_operational_diagnostic(self, draft: dict) -> tuple[str, float]:
        """Guardian's operational-diagnostic: LOCAL write (no chain dependency).

        2026-05-20. Guardian's lane is audits + ops (lane://audits/** +
        lane://ops/**); operational-diagnostic is the ops-side local skill
        (fleet-health / calibration / supervisor diagnostics absorbed into
        Guardian per agent_rationalization_v1.md). Like audit-drafting it does
        NOT touch chain — it must NOT be budget-gated as a chain op. The
        synthetic tx_hash format `local:diag:<draft_id>` distinguishes local
        diagnostic writes from chain operations in the spending_log audit trail.

        Returns (synthetic_local_tx_hash, 0.0).
        """
        draft_id = int(draft.get("id", 0) or 0)
        synthetic_tx_hash = f"local:diag:{draft_id}"
        cost_iotx = 0.0
        return synthetic_tx_hash, cost_iotx

    async def _exec_curator_listing_suspend(self, draft: dict) -> tuple[str, float]:
        """Curator's marketplace-listing-suspend: call chain.suspend_marketplace_listing.

        Returns (tx_hash, cost_iotx).
        """
        import json as _json
        try:
            payload = _json.loads(str(draft.get("payload_bytes_decoded", "{}")) or "{}")
        except Exception:
            payload = {}
        listing_id = str(payload.get("listing_id", "") or "")
        reason = str(payload.get("reason", "") or "operator-initiative-curator-autonomous")
        if not listing_id:
            raise ValueError("listing-suspend draft payload missing listing_id")
        # Chain helper may not exist yet — Path B v2 wires the suspend call
        # via VAPIDataMarketplaceListings.suspendListing(). For v1, surface
        # the missing-helper case as a clean refusal.
        suspend_fn = getattr(self.chain, "suspend_marketplace_listing", None)
        if suspend_fn is None:
            raise NotImplementedError("chain.suspend_marketplace_listing not yet wired (Path B v2)")
        result = await suspend_fn(listing_id=listing_id, reason=reason)
        tx_hash = str(result.get("tx_hash", "") or "")
        cost_iotx = float(result.get("cost_iotx", 0.0) or 0.0)
        return tx_hash, cost_iotx
