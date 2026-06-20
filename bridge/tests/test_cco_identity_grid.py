"""CCO Phase E — identity grid assembly tests."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from vapi_bridge.cco_identity_grid import assemble_identity_grid


@dataclass(frozen=True)
class _FakeReport:
    identity_class: str = "PATH_B_HOST_KEY"
    presence_ceiling_candidate: str = "P-T3"
    characterization_status: str = "PARTIAL_EDGE_ONLY"
    profile_id: str = "sony_dualshock_edge_v1"
    policy_ref: str = "CCO_T0_POLICY_v1_OPTION_C"


class TestAssembleIdentityGrid:
    def test_four_field_grid_from_oracle_and_path_a(self):
        grid = assemble_identity_grid(
            capability_report=_FakeReport(),
            signing_path="B",
            path_a_eligible=True,
            device_id="devX",
        )
        assert grid["identity_class"] == "PATH_B_HOST_KEY"
        assert grid["identity_axis"] == "Path B"
        assert grid["presence_ceiling_candidate"] == "P-T3"
        assert grid["signing_path"] == "B"
        assert grid["path_a_eligible"] is True
        assert grid["path_b_honesty_note"] is not None
        assert grid["composable_on_chain"] is False

    def test_signing_path_a_overrides_oracle_class(self):
        grid = assemble_identity_grid(
            capability_report=_FakeReport(identity_class="I0_SOFTWARE"),
            signing_path="A",
            path_a_eligible=True,
        )
        assert grid["identity_class"] == "I1_SILICON"
        assert grid["identity_axis"] == "I-1"
        assert grid["path_b_honesty_note"] is None

    def test_empty_fail_open(self):
        grid = assemble_identity_grid()
        assert grid["identity_class"] is None
        assert grid["presence_ceiling_candidate"] is None
        assert grid["signing_path"] is None
        assert grid["path_a_eligible"] is False
