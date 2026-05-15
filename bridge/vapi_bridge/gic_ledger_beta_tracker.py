"""Phase O5-MLGA Stage 5 (GIC-BETA autonomy) — GIC chain milestone tracker.

Second autonomous VPM artifact after MLGA-SESSION-v1. Wires the
`GIC-LEDGER-BETA-v1` compiler (scripts/vpm_compile_gic_ledger_beta.py)
to fire automatically every time the GIC chain crosses a 10-link
milestone (10, 20, 30, …, up to GIC_100 which is the headline
Phase 239 G3 anchor target).

Design discipline (mirrors mlga_session_tracker.py):
  • POLLING-based. Reads store.get_grind_chain_status() periodically.
  • NO FROZEN-region edits. No GIC chain primitive changes.
  • Opt-in via cfg.gic_ledger_beta_tracker_enabled (default False).
  • Single-task background coroutine; fail-open.
  • Idempotent: seeds _last_emitted_length from existing
    vpm_artifact_log rows on startup so bridge restarts don't
    re-emit milestones already shipped.

Milestone semantics:
  • Emit at chain_length ∈ {10, 20, 30, ..., 90, 100, 110, ...}
  • Each emission compiles a fresh HTML projection + persists a row
    in vpm_artifact_log with vpm_id='GIC-LEDGER-BETA-v1'.
  • The GIC_100 milestone IS the Phase 239 G3 on-chain-anchored
    artifact — when chain_length crosses 100 for the
    grind_phase235_v1 session, the tracker fills in the FROZEN
    Phase 239 G3 anchor tx_hash + block; earlier milestones leave
    those fields empty (on_chain_anchor=False).
  • zkba_manifest_hash_hex = latest_gic_hash (the chain head IS the
    canonical manifest hash for GIC-class artifacts; see
    Phase 239 G3 commit `e807347e…`).

WALLET-FREE; READ-ONLY against chain (no submissions, no anchor calls);
SQLite writes only to vpm_artifact_log + HTML to
frontend/src/artifacts/mlga/ (compiler-controlled).
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


# Default polling interval — chain advances ~10 links per minute during
# active play per MLGA tracker data (105 advances per 95s session).
# 30s cadence catches every 10-link milestone within ~3 minutes of
# crossing it.
_DEFAULT_POLL_INTERVAL_S: int = 30

# Milestone boundary. Emit at every multiple of this. 10 matches the
# GIC ledger publishing cadence used in the manual CLI invocations.
_MILESTONE_STEP: int = 10

# Phase 239 G3 on-chain anchor — FROZEN. The GIC_100 milestone for
# grind_phase235_v1 was anchored on IoTeX testnet on 2026-05-06 at
# block 43348052, tx 0xe807347e... Any artifact emitted for
# chain_length>=100 on this specific session carries these references.
# Future sessions / future anchor ceremonies will need their own
# pinning when those land.
_PHASE_239_G3_ANCHOR_SESSION: str = "grind_phase235_v1"
_PHASE_239_G3_ANCHOR_TX_HASH: str = (
    "0xe807347eb837a2ac9db0da51de7ddba5952a3e0e2509e197d9cac3375d23aa23"
)
_PHASE_239_G3_ANCHOR_BLOCK: int = 43348052


@dataclass(slots=True)
class GicLedgerBetaState:
    """In-memory tracker state."""
    last_emitted_length:    int = 0   # highest milestone already emitted
    emissions_this_session: int = 0   # count of emissions since bridge boot
    last_emit_ts_ns:        int = 0


def _resolve_genesis_hash_hex(
    grind_session_id: str, genesis_ts_ns: int,
) -> str:
    """Compute the GIC genesis hash for a given session.

    Delegates to grind_chain.genesis_gic per the FROZEN GIC formula v1.
    Returns hex string (no 0x prefix).
    """
    try:
        from .grind_chain import genesis_gic
        return genesis_gic(grind_session_id, int(genesis_ts_ns)).hex()
    except Exception as exc:  # noqa: BLE001 — fail-open
        log.warning(
            "GIC-BETA tracker: genesis_gic computation failed (%s); "
            "returning zero hash",
            exc,
        )
        return "00" * 32


def _resolve_anchor_for_milestone(
    *, grind_session_id: str, chain_length: int,
) -> tuple[str, int]:
    """Return (tx_hash, block) for the chain_length milestone, or ('', 0)
    if no anchor exists yet. Today only the Phase 239 G3 GIC_100
    anchor for grind_phase235_v1 is pinned."""
    if (
        chain_length >= 100
        and grind_session_id == _PHASE_239_G3_ANCHOR_SESSION
    ):
        return (_PHASE_239_G3_ANCHOR_TX_HASH, _PHASE_239_G3_ANCHOR_BLOCK)
    return ("", 0)


def _build_integrity_label(
    *, on_chain_anchor: bool, chain_length: int,
) -> Dict[str, Any]:
    """Construct the FROZEN 9-field integrity label dict for a
    GIC-LEDGER-BETA-v1 emission. Mirrors the CLI defaults at
    vpm_compile_gic_ledger_beta.py:316 but parameterized for the
    autonomous emission path (no consent involved — operator-owned
    grind session; on_chain_anchor depends on whether the milestone
    crossed the Phase 239 G3 line)."""
    return {
        "proof_type":             "VPM-GIC-LEDGER-BETA",
        "capture_mode":           "live",
        "raw_biometrics_exposed": False,
        "consent_active":         "n/a",
        "zk_verified":            False,
        "on_chain_anchor":        bool(on_chain_anchor),
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            "Autonomous GIC chain milestone emission "
            f"(crossed length={chain_length}); "
            "supplements lab measurements, does not replace them",
        ],
    }


class GicLedgerBetaTracker:
    """Autonomous GIC-LEDGER-BETA-v1 VPM emission tracker.

    On each poll cycle: reads grind chain status, computes the next
    milestone, and if the chain has crossed it since last emission,
    compiles + persists a VPM artifact.
    """

    def __init__(
        self,
        *,
        store,
        cfg,
        poll_interval_s: Optional[int] = None,
        milestone_step: Optional[int] = None,
    ) -> None:
        self._store = store
        self._cfg = cfg
        self._poll_interval_s = (
            poll_interval_s
            if poll_interval_s is not None
            else getattr(cfg, "gic_ledger_beta_interval_s", _DEFAULT_POLL_INTERVAL_S)
        )
        self._milestone_step = (
            milestone_step
            if milestone_step is not None
            else _MILESTONE_STEP
        )
        self._state = GicLedgerBetaState()
        self._state.last_emitted_length = self._seed_last_emitted_length()

    def _seed_last_emitted_length(self) -> int:
        """Read vpm_artifact_log on construction to recover the
        highest milestone already shipped. Survives bridge restarts."""
        try:
            db_path = getattr(self._store, "_db_path", None) or getattr(
                self._store, "db_path", None
            )
            if not db_path:
                return 0
            con = sqlite3.connect(db_path, timeout=2.0)
            try:
                con.row_factory = sqlite3.Row
                # Decode preimage_json to find max chain_length recorded.
                rows = con.execute(
                    "SELECT preimage_json FROM vpm_artifact_log "
                    "WHERE vpm_id = 'GIC-LEDGER-BETA-v1'"
                ).fetchall()
            finally:
                con.close()
            best = 0
            import json as _json
            for r in rows:
                pre = r["preimage_json"]
                if not pre:
                    continue
                try:
                    d = _json.loads(pre)
                    cl = int(d.get("gic_chain_length", 0))
                    if cl > best:
                        best = cl
                except Exception:
                    continue
            if best > 0:
                log.info(
                    "GIC-BETA tracker: seeded last_emitted_length=%d from "
                    "existing vpm_artifact_log rows", best,
                )
            return best
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning("GIC-BETA tracker: seed failed (%s); starting at 0", exc)
            return 0

    def poll_once(self) -> Dict[str, Any]:
        """Single poll cycle. Returns a result dict describing the
        action taken ('noop' / 'emitted'). Never raises."""
        try:
            grind_session_id = getattr(self._cfg, "grind_session_id", "") or ""
            if not grind_session_id:
                return {"action": "noop_no_grind_session"}

            status = self._store.get_grind_chain_status(
                grind_session_id, cfg=self._cfg,
            )
            chain_length = int(status.get("chain_length", 0))
            if chain_length <= 0:
                return {"action": "noop_no_chain"}

            # Next milestone we have NOT emitted yet
            next_milestone = (
                (self._state.last_emitted_length // self._milestone_step) + 1
            ) * self._milestone_step
            if chain_length < next_milestone:
                return {
                    "action": "noop_below_next_milestone",
                    "chain_length": chain_length,
                    "next_milestone": next_milestone,
                }

            # Crossed the next milestone — emit.
            return self._emit_milestone(
                grind_session_id=grind_session_id,
                status=status,
                milestone=next_milestone,
            )
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning("GIC-BETA tracker: poll_once error: %s", exc)
            return {"action": "error", "error": str(exc)}

    def _emit_milestone(
        self,
        *,
        grind_session_id: str,
        status: Dict[str, Any],
        milestone: int,
    ) -> Dict[str, Any]:
        """Compile + persist one GIC-LEDGER-BETA-v1 artifact at the
        given milestone. Fail-open: any failure logs + advances state
        so we don't tight-loop on a broken milestone."""
        try:
            chain_head_hex = (
                status.get("latest_gic_hash") or ""
            ).lower().removeprefix("0x")
            if len(chain_head_hex) != 64:
                log.warning(
                    "GIC-BETA tracker: chain head not 64 hex chars "
                    "(got %d); skipping milestone=%d",
                    len(chain_head_hex), milestone,
                )
                self._state.last_emitted_length = milestone
                return {"action": "skipped_invalid_head", "milestone": milestone}

            genesis_ts_ns = int((status.get("genesis_ts") or 0) * 1e9)
            genesis_hex = _resolve_genesis_hash_hex(
                grind_session_id, genesis_ts_ns,
            )
            anchor_tx, anchor_block = _resolve_anchor_for_milestone(
                grind_session_id=grind_session_id,
                chain_length=milestone,
            )
            on_chain_anchor = bool(anchor_tx and anchor_block > 0)

            integrity_label = _build_integrity_label(
                on_chain_anchor=on_chain_anchor,
                chain_length=milestone,
            )

            output_dir = (
                Path(__file__).resolve().parents[2]
                / "frontend" / "src" / "artifacts" / "gic_ledger_beta"
            )
            ts_ns = time.time_ns()

            # Import compile script lazily — dual-path mirroring MLGA
            # close-hook pattern (see scripts/mlga_compile_session_
            # artifact.py + commit 6a46cb53 / 669f829a / c032cf6e).
            import sys as _sys
            _scripts_path = str(
                Path(__file__).resolve().parents[2] / "scripts"
            )
            if _scripts_path not in _sys.path:
                _sys.path.insert(0, _scripts_path)
            from vpm_compile_gic_ledger_beta import (
                build_gic_ledger_beta_artifact,
            )

            manifest = build_gic_ledger_beta_artifact(
                gic_chain_head_hex=chain_head_hex,
                gic_chain_length=milestone,
                gic_genesis_hash_hex=genesis_hex,
                gic_genesis_ts_ns=genesis_ts_ns,
                on_chain_anchor_tx_hash=anchor_tx,
                on_chain_anchor_block=anchor_block,
                grind_session_id=grind_session_id,
                integrity_label=integrity_label,
                zkba_manifest_hash_hex=chain_head_hex,
                visual_state="live",
                capture_mode="live",
                output_dir=output_dir,
                ts_ns=ts_ns,
            )

            import json as _json
            preimage_json = _json.dumps({
                "vpm_id":             "GIC-LEDGER-BETA-v1",
                "grind_session_id":   grind_session_id,
                "gic_chain_length":   milestone,
                "gic_chain_head_hex": chain_head_hex,
                "gic_genesis_hash":   genesis_hex,
                "on_chain_anchor":    on_chain_anchor,
                "anchor_tx_hash":     anchor_tx,
                "anchor_block":       anchor_block,
                "ts_ns":              ts_ns,
            }, sort_keys=True, separators=(",", ":"))

            row_id = self._store.insert_vpm_artifact(
                commitment_hex=manifest.output_hash_hex,
                vpm_id="GIC-LEDGER-BETA-v1",
                zkba_class=2,             # ZKBAClass.GIC
                proof_weight=3,           # ProofWeightClass.CHAIN_ONLY
                visual_state="live",
                capture_mode="live",
                integrity_label_hash_hex=manifest.integrity_label_hash_hex,
                wrapper_schema="vapi-vpm-artifact-v1",
                zkba_manifest_hash_hex=chain_head_hex,
                manifest_uri=manifest.output_path,
                compiler_output_hash_hex=manifest.output_hash_hex,
                preimage_json=preimage_json,
                ts_ns=ts_ns,
            )

            self._state.last_emitted_length = milestone
            self._state.emissions_this_session += 1
            self._state.last_emit_ts_ns = ts_ns
            log.info(
                "GIC-BETA milestone emitted: chain_length=%d row=%d "
                "head=%s... on_chain=%s",
                milestone, row_id, chain_head_hex[:16], on_chain_anchor,
            )
            return {
                "action": "emitted",
                "milestone": milestone,
                "row": row_id,
                "commitment_hex": manifest.output_hash_hex,
            }
        except Exception as exc:  # noqa: BLE001 — fail-open
            import traceback as _tb
            log.warning(
                "GIC-BETA milestone %d emit failed: %s\n%s",
                milestone, exc, _tb.format_exc(),
            )
            # Advance past this milestone so we don't tight-loop. Operator
            # can clear by deleting the synthetic placeholder if needed.
            self._state.last_emitted_length = milestone
            return {"action": "error", "milestone": milestone, "error": str(exc)}


# ----------------------------------------------------------------------
# Async loop entry point (registers with main.py task slot)
# ----------------------------------------------------------------------

async def run_gic_ledger_beta_tracker_loop(
    *, tracker: GicLedgerBetaTracker, interval_s: Optional[int] = None,
) -> None:
    """Background coroutine — runs tracker.poll_once on a cadence.

    Mirrors run_mlga_session_tracker_loop pattern. Opt-in: bridge
    main.py only constructs this when
    cfg.gic_ledger_beta_tracker_enabled=True. Fail-open: poll_once
    already catches its own exceptions.
    """
    if interval_s is None:
        interval_s = tracker._poll_interval_s
    log.info(
        "Phase O5-MLGA Stage 5: GIC-BETA tracker started "
        "(interval=%ds, milestone_step=%d, seeded_at=%d)",
        interval_s, tracker._milestone_step,
        tracker._state.last_emitted_length,
    )
    try:
        while True:
            tracker.poll_once()
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        log.info("GIC-BETA tracker cancelled")
        raise
