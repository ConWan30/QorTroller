"""Phase 235.x-STABILITY-3 (WIF-066+): DataCuratorAgent kill-switch gating.

When CHAIN_SUBMISSION_PAUSED is held, every oracle update tx short-circuits
at chain._send_tx — but the per-device iteration still constructs
devices*3 method invocations + gate checks, each consuming event-loop time
and starving HTTP/MLGA tasks (observed: 26862-device pass blocking
/operator/* endpoints for >180s).

T-CURATOR-KS-1   When chain_submission_paused=True, _run_curation_cycle
                 returns immediately without consuming the device list or
                 calling _curate_device.
T-CURATOR-KS-2   When chain_submission_paused=False, _run_curation_cycle
                 iterates devices + calls _curate_device per device.
T-CURATOR-KS-3   When chain_submission_paused attr is missing on cfg
                 (default-safe via getattr), curator proceeds normally
                 (backward-compat for cfgs predating the flag).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_agent(*, chain_paused: bool | None, devices: list[str]):
    """Wire a minimal DataCuratorAgent with mock cfg/store/chain.

    chain_paused=None -> cfg has no chain_submission_paused attr at all
    (tests the default-safe getattr() fallback at T-CURATOR-KS-3).
    """
    from vapi_bridge.data_curator_agent import DataCuratorAgent

    cfg = MagicMock()
    cfg.curator_enabled = True
    cfg.curator_oracle_publish = True
    if chain_paused is None:
        if hasattr(cfg, "chain_submission_paused"):
            del cfg.chain_submission_paused
        cfg = MagicMock(spec=["curator_enabled", "curator_oracle_publish"])
        cfg.curator_enabled = True
        cfg.curator_oracle_publish = True
    else:
        cfg.chain_submission_paused = chain_paused

    store = MagicMock()
    store.list_known_devices = MagicMock(return_value=list(devices))

    chain = MagicMock()
    agent = DataCuratorAgent(cfg=cfg, store=store, chain=chain)
    # Replace _curate_device with an AsyncMock so we can assert call count
    # without exercising the full per-device curation chain.
    agent._curate_device = AsyncMock(return_value=None)
    return agent, store


# ----- T-CURATOR-KS-1 -----

def test_t_curator_ks_1_skips_iteration_when_paused():
    """chain_submission_paused=True -> cycle returns before list_known_devices."""
    agent, store = _make_agent(
        chain_paused=True,
        devices=["dev_aaa", "dev_bbb", "dev_ccc"],
    )
    asyncio.run(agent._run_curation_cycle())
    # Critical assertion: the device list was NEVER consumed
    store.list_known_devices.assert_not_called()
    # And no _curate_device call fired
    agent._curate_device.assert_not_called()


# ----- T-CURATOR-KS-2 -----

def test_t_curator_ks_2_iterates_when_unpaused():
    """chain_submission_paused=False -> iteration proceeds (3 devices -> 3 calls)."""
    agent, store = _make_agent(
        chain_paused=False,
        devices=["dev_aaa", "dev_bbb", "dev_ccc"],
    )
    asyncio.run(agent._run_curation_cycle())
    store.list_known_devices.assert_called_once()
    assert agent._curate_device.call_count == 3
    called_with = [call.args[0] for call in agent._curate_device.call_args_list]
    assert called_with == ["dev_aaa", "dev_bbb", "dev_ccc"]


# ----- T-CURATOR-KS-3 -----

def test_t_curator_ks_3_backward_compat_when_flag_missing():
    """cfg without chain_submission_paused attr -> default-safe (proceeds)."""
    agent, store = _make_agent(
        chain_paused=None,    # attr absent entirely
        devices=["dev_xyz"],
    )
    asyncio.run(agent._run_curation_cycle())
    store.list_known_devices.assert_called_once()
    assert agent._curate_device.call_count == 1
