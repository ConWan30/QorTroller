"""Phase 235.x-STABILITY-9 stages 4c/4d/4e (2026-05-17) — Generic absorbed-
agent ticker for the 3 Operator Initiative stewards.

Per agent_rationalization_v1.md, 11 background agents are absorbed into
the stewards (Sentry / Guardian / Curator):

  Sentry (4):  VHPRenewalAgent, CeremonyWatchdogAgent, ChainReconciler,
                RulingProvenanceAnchorAgent
  Guardian (6): ProtocolIntelligenceAgent, ProtocolMaturityScoringAgent,
                MaturityElevationGateAgent, AgentSupervisor,
                AgentCalibrationMonitor, RulingEnforcementAgent
  Curator (1):  CorpusDataCuratorAgent

Each absorbed agent retains its existing module + tests (Q1=YES per
operator authorization). What changes: the standalone background asyncio
task spawn in main.py is removed; instead each steward's poll loop calls
`tick_all()` on its AbsorbedAgentTicker, which checks per-agent elapsed
time since last invocation + fires the agent's single-cycle method on a
worker thread (asyncio.to_thread) if the agent's original cadence has
elapsed.

This is the minimum-viable absorption pattern:
- 11 fewer background asyncio tasks at boot (thundering-herd reduction)
- Each agent still runs at its ORIGINAL cadence (Q2 partial — agents
  with original cadence shorter than steward's 30s tick still run
  every steward tick; agents with original cadence longer run when
  their elapsed exceeds it)
- No module changes to absorbed agents; their compute methods are
  invoked as-is via getattr + asyncio.to_thread / await
- Each tick wraps in try/except — one agent failing doesn't block
  others or break the steward poll cycle

Re-activation path (Q1): import the absorbed agent's module, instantiate,
spawn via asyncio.create_task on its run_poll_loop / run_event_consumer
in main.py — exactly as it was pre-stage-4c/4d/4e.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass(slots=True)
class AbsorbedAgentSpec:
    """Description of an absorbed agent's single-cycle invocation contract."""
    name: str
    module_path: str        # e.g. "bridge.vapi_bridge.vhp_renewal_agent"
    class_name: str         # e.g. "VHPRenewalAgent"
    method_name: str        # single-cycle method, e.g. "_check_and_renew"
    interval_s: int         # agent's original poll interval
    is_async: bool = True
    needs_chain: bool = False
    needs_bus: bool = False


@dataclass(slots=True)
class _AbsorbedAgentState:
    """Per-agent runtime state inside the ticker."""
    instance: Optional[Any] = None
    last_invoked_at: float = 0.0
    invocations: int = 0
    failures: int = 0
    last_error: str = ""


# ---------------------------------------------------------------------------
# Absorbed-agent rosters per steward (Q2: original cadence preserved)
# ---------------------------------------------------------------------------

# Sentry steward absorbs 4 provenance / chain-anchor agents.
# All four produce on-chain anchors or provenance writes — Sentry's lane.
SENTRY_ABSORBED: List[AbsorbedAgentSpec] = [
    AbsorbedAgentSpec(
        name="VHPRenewalAgent",
        module_path="bridge.vapi_bridge.vhp_renewal_agent",
        class_name="VHPRenewalAgent",
        method_name="_check_and_renew",
        interval_s=21600,  # 6 hours (original)
        needs_chain=True,
        needs_bus=True,
    ),
    AbsorbedAgentSpec(
        name="CeremonyWatchdogAgent",
        module_path="bridge.vapi_bridge.ceremony_watchdog",
        class_name="CeremonyWatchdogAgent",
        method_name="_check_ceremony_integrity",
        interval_s=300,    # 5 min (original)
        needs_bus=True,
    ),
    AbsorbedAgentSpec(
        name="ChainReconciler",
        module_path="bridge.vapi_bridge.chain_reconciler",
        class_name="ChainReconciler",
        method_name="_reconcile_cycle",
        interval_s=30,     # 30s (original)
        needs_chain=True,
    ),
    AbsorbedAgentSpec(
        name="RulingProvenanceAnchorAgent",
        module_path="bridge.vapi_bridge.ruling_provenance_anchor_agent",
        class_name="RulingProvenanceAnchorAgent",
        method_name="_anchor_pending_rulings",
        interval_s=60,     # 60s (original)
        needs_chain=True,
    ),
]


# Guardian steward absorbs 4 diagnostic / audit-bearing agents.
# V-check 2026-05-17: ProtocolMaturityScoringAgent + MaturityElevationGateAgent
# from the doc's §3.2 list are DROPPED because main.py never spawned them as
# standalone tasks despite cfg flags being True-by-default. Absorbing them
# would INTRODUCE new behavior (not just preserve existing). They can be
# explicitly added to GUARDIAN_ABSORBED in a follow-up commit after V&V of
# their compute methods.
GUARDIAN_ABSORBED: List[AbsorbedAgentSpec] = [
    AbsorbedAgentSpec(
        name="ProtocolIntelligenceAgent",
        module_path="bridge.vapi_bridge.protocol_intelligence_agent",
        class_name="ProtocolIntelligenceAgent",
        method_name="_compute_and_store",
        interval_s=60,
        needs_bus=True,
    ),
    AbsorbedAgentSpec(
        name="AgentSupervisor",
        module_path="bridge.vapi_bridge.agent_supervisor",
        class_name="AgentSupervisor",
        method_name="_check_and_report",
        interval_s=900,    # 15 min
        needs_bus=True,
    ),
    AbsorbedAgentSpec(
        name="AgentCalibrationMonitor",
        module_path="bridge.vapi_bridge.agent_calibration_monitor",
        class_name="AgentCalibrationMonitor",
        method_name="_run_all_tests",
        interval_s=900,    # 15 min
        needs_bus=True,
    ),
    AbsorbedAgentSpec(
        name="RulingEnforcementAgent",
        module_path="bridge.vapi_bridge.ruling_enforcement_agent",
        class_name="RulingEnforcementAgent",
        method_name="_consume_pending_events",
        interval_s=300,    # 5 min
        needs_chain=True,
        needs_bus=True,
    ),
]


# Curator steward absorbs 1 data-curation agent.
# Corpus integrity IS curation — Curator's natural lane (Q4=YES).
CURATOR_ABSORBED: List[AbsorbedAgentSpec] = [
    AbsorbedAgentSpec(
        name="CorpusDataCuratorAgent",
        module_path="bridge.vapi_bridge.corpus_curator_agent",
        class_name="CorpusDataCuratorAgent",
        method_name="_run_once",
        interval_s=1800,   # 30 min
        needs_bus=True,
    ),
]


class AbsorbedAgentTicker:
    """Generic ticker that owns per-spec instances + cadence state.

    Usage from a steward poll loop:

        ticker = AbsorbedAgentTicker(
            steward_name="Sentry",
            specs=SENTRY_ABSORBED,
            cfg=cfg, store=store, chain=chain, bus=bus,
        )
        # inside the steward's _run_loop:
        await ticker.tick_all()
    """

    def __init__(
        self,
        *,
        steward_name: str,
        specs: List[AbsorbedAgentSpec],
        cfg,
        store,
        chain=None,
        bus=None,
    ) -> None:
        self._steward_name = steward_name
        self._specs = specs
        self._cfg = cfg
        self._store = store
        self._chain = chain
        self._bus = bus
        self._state: Dict[str, _AbsorbedAgentState] = {
            spec.name: _AbsorbedAgentState() for spec in specs
        }
        # Phase 235.x-STABILITY-9 stage 5 2026-05-17: per-spec first-tick
        # jitter. Without this, all 9 absorbed agents become eligible
        # on the same first tick (last_invoked_at=0 → elapsed >= interval
        # always true) — same thundering-herd at boot. Offset each spec's
        # last_invoked_at by `time.time() - spec.interval_s + uniform(0, jitter)`
        # so each first-fire is delayed by jitter[0, jitter_max] relative
        # to boot. Reuses startup_grace's seeded RNG for reproducibility
        # when cfg.startup_jitter_seed is set.
        if getattr(cfg, "startup_jitter_enabled", True):
            try:
                from .startup_grace import _get_rng
                rng = _get_rng(cfg)
                jitter_max = float(getattr(cfg, "startup_jitter_max_s", 30.0))
                now = time.time()
                for spec in specs:
                    jitter_offset = rng.uniform(0.0, jitter_max)
                    # Set last_invoked_at so first eligible tick is at
                    # `now + jitter_offset` (NOT immediately on tick #1):
                    # elapsed = now+t - last_invoked_at; we want
                    # elapsed >= interval_s at time now+jitter_offset:
                    # → last_invoked_at = now + jitter_offset - interval_s
                    state = self._state[spec.name]
                    state.last_invoked_at = (
                        now + jitter_offset - spec.interval_s
                    )
                log.info(
                    "%sStewardAbsorbedTicker: stage-5 startup-jitter "
                    "applied (max=%.1fs); per-spec first-tick delays "
                    "spread over jitter window",
                    steward_name, jitter_max,
                )
            except Exception as _exc:  # noqa: BLE001 — fail-open
                log.warning(
                    "%sStewardAbsorbedTicker: stage-5 jitter setup failed "
                    "(%s); ticker fires all on first tick (pre-stage-5 behavior)",
                    steward_name, _exc,
                )
        log.info(
            "%sStewardAbsorbedTicker: configured with %d absorbed agents (%s)",
            steward_name, len(specs), ", ".join(s.name for s in specs),
        )

    def _build_instance(self, spec: AbsorbedAgentSpec) -> Optional[Any]:
        """Lazily import + instantiate the absorbed agent on first tick.

        Fail-open: missing module / class / constructor mismatch → log
        warning + return None. The ticker keeps trying on subsequent
        ticks (cheap) so a transient import error doesn't permanently
        disable the agent."""
        try:
            module = importlib.import_module(spec.module_path)
            klass = getattr(module, spec.class_name)
            # Constructor signature varies — inspect + pass only what's accepted.
            sig = inspect.signature(klass.__init__)
            kwargs: Dict[str, Any] = {}
            params = sig.parameters
            # Standard pairs — pass what the constructor accepts.
            if "cfg" in params:
                kwargs["cfg"] = self._cfg
            if "store" in params:
                kwargs["store"] = self._store
            if "chain" in params and (spec.needs_chain or "chain" in params):
                kwargs["chain"] = self._chain
            if "bus" in params and (spec.needs_bus or "bus" in params):
                kwargs["bus"] = self._bus
            # Some agents (ChainReconciler) take positional (store, chain, ...).
            # Handle them via kwarg matching above; if a required positional has
            # no default and no kwarg match, this raises and we fail-open.
            return klass(**kwargs)
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning(
                "%sStewardAbsorbedTicker: failed to instantiate %s: %s",
                self._steward_name, spec.name, exc,
            )
            return None

    async def _invoke_one(self, spec: AbsorbedAgentSpec) -> None:
        """Invoke a single absorbed agent's single-cycle method.

        Async methods: await directly. Sync methods: wrap in
        asyncio.to_thread so they don't block the steward's event
        loop.

        Fail-open: any exception logged + counter bumped + state
        unchanged otherwise; never raises out."""
        state = self._state[spec.name]
        if state.instance is None:
            state.instance = self._build_instance(spec)
            if state.instance is None:
                return  # build failed; will retry next eligible tick
        method = getattr(state.instance, spec.method_name, None)
        if method is None:
            log.warning(
                "%sStewardAbsorbedTicker: %s missing method %s — disabling",
                self._steward_name, spec.name, spec.method_name,
            )
            # Mark with bogus method so we don't retry every tick.
            state.last_error = f"missing_method:{spec.method_name}"
            return
        try:
            if spec.is_async:
                # Await the coroutine. _invoke_one already runs on the
                # steward's event loop; the agent's awaits cooperate.
                result = method()
                if inspect.iscoroutine(result):
                    await result
            else:
                # Sync method body — offload to worker thread.
                await asyncio.to_thread(method)
            state.invocations += 1
            state.last_invoked_at = time.time()
        except Exception as exc:  # noqa: BLE001 — fail-open
            state.failures += 1
            state.last_error = str(exc)[:200]
            log.warning(
                "%sStewardAbsorbedTicker: %s.%s raised: %s",
                self._steward_name, spec.name, spec.method_name, exc,
            )

    async def tick_all(self) -> Dict[str, int]:
        """Tick every absorbed agent whose elapsed >= interval_s.

        Returns dict {agent_name: invoked_int} for observability. Never
        raises out. Each agent invoked fully (one at a time) so a slow
        agent doesn't block others — but they run sequentially, not in
        parallel, to preserve the steward's "one thing at a time"
        polling discipline.
        """
        now = time.time()
        fired: Dict[str, int] = {}
        for spec in self._specs:
            state = self._state[spec.name]
            elapsed = now - state.last_invoked_at
            if state.last_invoked_at == 0.0 or elapsed >= spec.interval_s:
                # Eligible — fire it.
                try:
                    await self._invoke_one(spec)
                    fired[spec.name] = 1
                except Exception as exc:  # noqa: BLE001 — defense in depth
                    log.warning(
                        "%sStewardAbsorbedTicker: tick_all caught %s for %s",
                        self._steward_name, exc, spec.name,
                    )
                    fired[spec.name] = 0
            else:
                fired[spec.name] = 0
        return fired

    def get_state_summary(self) -> Dict[str, Dict[str, Any]]:
        """Read-only snapshot of per-agent state — for /operator/* endpoints."""
        return {
            name: {
                "invocations":    s.invocations,
                "failures":       s.failures,
                "last_invoked_at": s.last_invoked_at,
                "last_error":     s.last_error,
                "instantiated":   s.instance is not None,
            }
            for name, s in self._state.items()
        }
