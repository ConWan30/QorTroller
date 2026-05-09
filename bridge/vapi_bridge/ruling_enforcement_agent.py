"""
Phase 66 — RulingEnforcementAgent: streak escalation + on-chain commitment.

Closes the enforcement loop opened by Phase 65 SessionAdjudicator:
  ruling_completed event → streak update → escalation check
  → on-chain RulingRegistry.recordRuling() → PHGCredential.suspend() on BLOCK
  → ruling_enforced reply event to bridge_agent

Cross-references BehavioralArchaeologist warmup_attack_score (READ-ONLY):
  warmup_attack_score > 0.7 → 7-day suspension instead of 24h default.

Parallel to InsightSynthesizer Mode 5 (risk-label path) — both paths can
suspend PHGCredential independently. No threshold writes — CalibrationAgent owns that.
"""

import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S    = 300   # 5 minutes — matches SessionAdjudicator cadence
_FLAG_STREAK_THRESH = 5     # FLAG×5 → escalate to HOLD
_HOLD_STREAK_THRESH = 2     # HOLD×2 → escalate to BLOCK
_SUSPEND_DEFAULT_S  = 86400    # 24h default suspension
_SUSPEND_WARMUP_S   = 604800   # 7d for confirmed warmup attackers


class RulingEnforcementAgent:
    """
    Autonomous ruling enforcement background agent (Phase 66).

    Reads ruling_completed events targeted at this agent (source: session_adjudicator).
    For each event:
      1. upsert_ruling_streak — increment or reset streak counter
      2. Check escalation thresholds — FLAG×5→HOLD, HOLD×2→BLOCK
      3. chain.record_ruling_on_chain() — commit to RulingRegistry.sol (best-effort)
      4. store.insert_on_chain_ruling() — persist tx_hash
      5. If effective_verdict==BLOCK: _enforce_block() → PHGCredential.suspend()
      6. mark_event_consumed + write ruling_enforced reply event to bridge_agent

    chain=None: on-chain and credential enforcement steps silently skipped.
    ruling_enforcement_enabled=False in config: agent still runs but skips enforcement.
    Consecutive failure counter: ≥3 → log.error (same pattern as CalibrationAgent).
    """

    def __init__(self, cfg, store, chain=None, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._chain = chain
        self._bus   = bus

    @property
    def _block_threshold(self) -> int:
        return getattr(self._cfg, "ruling_streak_block_threshold", 3)

    async def _listen_live_mode_bus(self) -> None:
        """Phase 97 — Subscribe to live_mode_enabled for fleet-wide mode shift. Never raises."""
        try:
            queue = await self._bus.subscribe("live_mode_enabled")
            while True:
                try:
                    import asyncio as _aio
                    event = await _aio.wait_for(queue.get(), timeout=300.0)
                    payload = event.get("payload", event) if isinstance(event, dict) else {}
                    dry_run_val = payload.get("dry_run", None)
                    if dry_run_val is not None:
                        self._cfg.agent_dry_run_mode = bool(dry_run_val)
                        log.info(
                            "RulingEnforcementAgent: live_mode_enabled — agent_dry_run_mode=%s",
                            bool(dry_run_val),
                        )
                except _aio.TimeoutError:
                    pass
                except _aio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning("RulingEnforcementAgent: _listen_live_mode_bus error: %s", exc)
                    # Phase 235.x-STABILITY-7: defensive backoff
                    try:
                        await _aio.sleep(min(300.0, 5.0))
                    except _aio.CancelledError:
                        raise
                    except Exception as backoff_exc:
                        log.error(
                            "RulingEnforcementAgent: _listen_live_mode_bus "
                            "backoff sleep failed (%s) — exiting cleanly",
                            backoff_exc,
                        )
                        return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("RulingEnforcementAgent: _listen_live_mode_bus setup failed: %s", exc)

    async def run_event_consumer(self) -> None:
        """Background loop: poll every 5 minutes for ruling_completed events."""
        log.info(
            "RulingEnforcementAgent started (Phase 67) poll=%ds block_threshold=%d",
            _POLL_INTERVAL_S, self._block_threshold,
        )
        # Phase 97: subscribe to live_mode_enabled for fleet-wide mode shift
        if self._bus is not None:
            import asyncio as _asyncio
            _asyncio.ensure_future(self._listen_live_mode_bus())
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._consume_pending_events()
                await self._check_expired_suspensions()  # Phase 67: auto-reinstate
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "RulingEnforcementAgent: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("RulingEnforcementAgent: cycle error: %s", exc)
                # Phase 235.x-STABILITY-6: defensive backoff (see chain_reconciler).
                try:
                    await asyncio.sleep(min(_POLL_INTERVAL_S, 5.0))
                except asyncio.CancelledError:
                    raise
                except Exception as backoff_exc:
                    log.error(
                        "RulingEnforcementAgent: backoff sleep failed (%s) — "
                        "exiting loop cleanly", backoff_exc,
                    )
                    return

    async def _consume_pending_events(self) -> None:
        events = self._store.read_unconsumed_events("ruling_enforcement_agent", limit=20)
        if not events:
            return
        log.info(
            "RulingEnforcementAgent: processing %d ruling_completed event(s)", len(events)
        )
        for event in events:
            if event.get("event_type") != "ruling_completed":
                continue
            try:
                await self._process_ruling_completed(event)
            except Exception as exc:
                log.warning(
                    "RulingEnforcementAgent: enforcement failed for event %s: %s",
                    event.get("id"), exc,
                )

    async def _process_ruling_completed(self, event: dict) -> None:
        payload   = json.loads(event.get("payload_json", "{}"))
        device_id = payload.get("device_id", "")
        ruling_id = payload.get("ruling_id")
        verdict   = payload.get("verdict", "FLAG")
        if not device_id or ruling_id is None:
            return

        ruling = self._store.get_agent_ruling_by_id(ruling_id)
        if not ruling:
            log.warning("RulingEnforcementAgent: ruling_id %s not found", ruling_id)
            return

        # 1+2. Streak update + escalation
        streak       = self._store.upsert_ruling_streak(device_id, verdict, ruling_id)
        streak_count = streak.get("current_streak", 1)
        effective_verdict = verdict

        if verdict == "FLAG" and streak_count >= _FLAG_STREAK_THRESH:
            effective_verdict = "HOLD"
            self._store.set_streak_escalation(device_id, "HOLD")
            log.info(
                "RulingEnforcementAgent: FLAG x%d -> HOLD for %s",
                streak_count, device_id[:12],
            )
        elif verdict == "HOLD" and streak_count >= _HOLD_STREAK_THRESH:
            effective_verdict = "BLOCK"
            self._store.set_streak_escalation(device_id, "BLOCK")
            log.info(
                "RulingEnforcementAgent: HOLD x%d -> BLOCK for %s",
                streak_count, device_id[:12],
            )

        # 3+4. On-chain commitment (best-effort)
        commitment_hex = ruling.get("commitment_hash", "")
        tx_hash = None
        if self._chain and commitment_hex:
            try:
                ts_ns = int(ruling.get("created_at", time.time()) * 1e9)
                tx_hash = await self._chain.record_ruling_on_chain(
                    commitment_hash_bytes=bytes.fromhex(commitment_hex),
                    device_id_hex=device_id,
                    verdict=effective_verdict,
                    confidence=ruling.get("confidence", 0.5),
                    timestamp_ns=ts_ns,
                )
                self._store.insert_on_chain_ruling(
                    ruling_id=ruling_id,
                    device_id=device_id,
                    commitment_hash=commitment_hex,
                    tx_hash=tx_hash,
                )
                log.info(
                    "RulingEnforcementAgent: on-chain %s...->tx %s...",
                    commitment_hex[:12], tx_hash[:12],
                )
                # Phase 79/80: publish ruling_block_committed to bus on BLOCK
                if effective_verdict == "BLOCK" and self._bus is not None:
                    try:
                        import asyncio as _asyncio
                        _asyncio.ensure_future(self._bus.publish(
                            "ruling_block_committed",
                            {
                                "device_id": device_id,
                                "ruling_id": ruling_id,
                                "commitment_hash": commitment_hex,
                                "tx_hash": tx_hash,
                                "verdict": effective_verdict,
                            },
                            "ruling_enforcement_agent",
                        ))
                    except Exception as _bus_exc:
                        log.debug(
                            "RulingEnforcementAgent: bus publish failed: %s", _bus_exc
                        )
            except Exception as exc:
                log.warning("RulingEnforcementAgent: on-chain record failed: %s", exc)

        # 5. Credential enforcement on BLOCK
        if effective_verdict == "BLOCK":
            if getattr(self._cfg, "enforcement_shadow_mode", False):
                # Phase 90: Shadow mode — log what would happen, skip actual suspend
                await self._shadow_block(device_id, ruling)
            else:
                await self._enforce_block(device_id, ruling)

        # 6. Mark consumed + reply event
        self._store.mark_event_consumed(event["id"], "ruling_enforcement_agent")
        self._store.write_agent_event(
            event_type="ruling_enforced",
            payload=json.dumps({
                "device_id":        device_id,
                "ruling_id":        ruling_id,
                "verdict":          verdict,
                "effective_verdict": effective_verdict,
                "streak_count":     streak_count,
                "tx_hash":          tx_hash,
            }),
            source="ruling_enforcement_agent",
            target="bridge_agent",
            device_id=device_id,
        )
        log.info(
            "RulingEnforcementAgent: enforced ruling %s -> %s (streak=%d tx=%s) for %s",
            ruling_id, effective_verdict, streak_count,
            tx_hash[:12] if tx_hash else "none", device_id[:12],
        )

    async def _shadow_block(self, device_id: str, ruling: dict) -> None:
        """Phase 90 — Shadow enforcement: record what BLOCK would do, skip PHGCredential.suspend().

        Writes to shadow_enforcement_log. would_have_suspended=1 always (every BLOCK counts).
        Operators review GET /agent/shadow-enforcement-log to validate false-positive rate
        before setting ENFORCEMENT_SHADOW_MODE=false for real enforcement.
        """
        trajectory = self._store.get_device_risk_label(device_id) or {}
        warmup_score = float(trajectory.get("warmup_attack_score", 0.0) or 0.0)
        duration_s = _SUSPEND_WARMUP_S if warmup_score > 0.7 else _SUSPEND_DEFAULT_S
        commitment_hex = ruling.get("commitment_hash", "0" * 64)
        ruling_id = ruling.get("id")
        self._store.insert_shadow_enforcement_log(
            device_id=device_id,
            ruling_id=ruling_id,
            commitment_hash=commitment_hex,
            would_have_suspended=1,
            duration_s=duration_s,
            warmup_attack_score=warmup_score,
        )
        log.info(
            "RulingEnforcementAgent: SHADOW BLOCK device=%s duration_s=%d warmup=%.2f "
            "(shadow_mode=true — no real suspension)",
            device_id[:12], duration_s, warmup_score,
        )

    async def _enforce_block(self, device_id: str, ruling: dict) -> None:
        """Suspend PHGCredential on BLOCK. Cross-references warmup_attack_score."""
        if not self._chain:
            log.info(
                "RulingEnforcementAgent: BLOCK for %s — no chain client, skipping suspend",
                device_id[:12],
            )
            return

        # Read warmup_attack_score from BehavioralArchaeologist (READ-ONLY)
        trajectory   = self._store.get_device_risk_label(device_id) or {}
        warmup_score = float(trajectory.get("warmup_attack_score", 0.0) or 0.0)
        duration_s   = _SUSPEND_WARMUP_S if warmup_score > 0.7 else _SUSPEND_DEFAULT_S

        if warmup_score > 0.7:
            log.warning(
                "RulingEnforcementAgent: warmup_attack_score=%.2f -> 7-day suspension %s",
                warmup_score, device_id[:12],
            )

        commitment_hex = ruling.get("commitment_hash", "0" * 64)
        try:
            commitment_bytes = bytes.fromhex(commitment_hex)
            await self._chain.suspend_phg_credential(device_id, commitment_bytes, duration_s)
            # Phase 67 fix: correct arg order — evidence_hash (str), until (float timestamp)
            self._store.store_credential_suspension(
                device_id,
                commitment_hex,
                time.time() + duration_s,
            )
            log.info(
                "RulingEnforcementAgent: PHGCredential suspended %ds for %s",
                duration_s, device_id[:12],
            )
        except Exception as exc:
            log.warning("RulingEnforcementAgent: credential suspend failed: %s", exc)

    async def _check_expired_suspensions(self) -> None:
        """Phase 67 — Auto-reinstate PHGCredential after suspension window expires.

        Queries credential_enforcement for rows where suspended_until < now() and
        reinstated=0. For each: reinstate_phg_credential() on-chain, mark DB as
        reinstated, reset ruling_streak to CLEAR so device starts clean.
        chain=None: silently skipped (offline-safe).
        """
        if not self._chain:
            return
        try:
            expired = self._store.get_expired_suspensions()
        except Exception as exc:
            log.warning("RulingEnforcementAgent: get_expired_suspensions failed: %s", exc)
            return
        for row in expired:
            device_id = row.get("device_id", "")
            if not device_id:
                continue
            try:
                await self._chain.reinstate_phg_credential(device_id)
                self._store.mark_suspension_reinstated(device_id)
                self._store.upsert_ruling_streak(device_id, "CLEAR", 0)
                log.info(
                    "RulingEnforcementAgent: auto-reinstated PHGCredential for %s",
                    device_id[:12],
                )
            except Exception as exc:
                log.warning(
                    "RulingEnforcementAgent: auto-reinstate failed for %s: %s",
                    device_id[:12], exc,
                )
