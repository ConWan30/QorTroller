"""
Retina Visual Oracle — pytest entrypoint for the game-aware VLM unit tests.

The source-of-truth test functions live in
`vapi_bridge.retina_visual_oracle` (inline, runnable via
`python bridge/vapi_bridge/retina_visual_oracle.py`). This module re-exports
them so the bridge test suite collects and runs them under pytest.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.retina_visual_oracle import (  # noqa: E402
    test_visual_context_defaults,
    test_football_prompt_contains_football_fields,
    test_shooter_prompt_contains_shooter_fields,
    test_prompt_selection,
    test_football_parse_response,
    test_football_to_dict,
    test_shooter_to_dict,
    test_cross_modal_match,
    test_cross_modal_anomaly,
    test_cross_modal_no_visual,
    test_json_extraction,
    test_shooter_parse_response,
    test_config_football_detection,
    test_football_config_disables_shooter_fields,
    test_visual_oracle_sampling,
    test_football_events_constants,
)

__all__ = [
    "test_visual_context_defaults",
    "test_football_prompt_contains_football_fields",
    "test_shooter_prompt_contains_shooter_fields",
    "test_prompt_selection",
    "test_football_parse_response",
    "test_football_to_dict",
    "test_shooter_to_dict",
    "test_cross_modal_match",
    "test_cross_modal_anomaly",
    "test_cross_modal_no_visual",
    "test_json_extraction",
    "test_shooter_parse_response",
    "test_config_football_detection",
    "test_football_config_disables_shooter_fields",
    "test_visual_oracle_sampling",
    "test_football_events_constants",
]
