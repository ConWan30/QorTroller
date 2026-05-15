"""Phase O5-PUBLIC-VIEWER — INV-PUBLIC-FORENSIC-001 grep-CI guard tests.

Static-grep guards on the public sub-app source. These exist to catch
accidental introduction of operator-auth gates into a route that's
declared public — a class of regression that would silently leak
private operator data through a no-auth surface.

T-PUB-NOAUTH-1   public_forensic_api.py contains NO `_check_key(` substring
T-PUB-NOAUTH-2   public_forensic_api.py contains NO `_check_read_key(` substring
T-PUB-NOAUTH-3   main.py mounts the public app at exactly `/public` path
T-PUB-NOAUTH-4   public sub-app has CORS expose-headers for 5 X-VAME-* keys
T-PUB-NOAUTH-5   FROZEN-v1 algorithm manifest carries 14 named tags
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


# ----- T-1 -----

def test_t_pub_noauth_1_no_check_key_calls():
    src = (ROOT / "bridge" / "vapi_bridge" / "public_forensic_api.py").read_text()
    assert "_check_key(" not in src, (
        "INV-PUBLIC-FORENSIC-001 violated: _check_key( appeared in "
        "public_forensic_api.py. This would gate a public route with "
        "operator auth — fix before commit."
    )


# ----- T-2 -----

def test_t_pub_noauth_2_no_check_read_key_calls():
    src = (ROOT / "bridge" / "vapi_bridge" / "public_forensic_api.py").read_text()
    assert "_check_read_key(" not in src, (
        "INV-PUBLIC-FORENSIC-001 violated: _check_read_key( appeared "
        "in public_forensic_api.py — same fix as T-PUB-NOAUTH-1."
    )


# ----- T-3 -----

def test_t_pub_noauth_3_mount_path_pinned():
    src = (ROOT / "bridge" / "vapi_bridge" / "main.py").read_text()
    # The literal mount call MUST appear with exactly /public, not
    # /pubic / /pub / /public2 / etc.
    assert 'app.mount("/public",' in src, (
        "INV-PUBLIC-FORENSIC-002 violated: public sub-app mount path "
        "must be exactly /public in main.py"
    )


# ----- T-4 -----

def test_t_pub_noauth_4_cors_expose_vame_headers():
    src = (ROOT / "bridge" / "vapi_bridge" / "public_forensic_api.py").read_text()
    for header in [
        "X-VAME-Version", "X-VAME-Commitment", "X-VAME-Chain-Head",
        "X-VAME-TS-NS",   "X-VAME-Endpoint",
    ]:
        assert header in src, (
            f"CORS expose-headers must include {header} so the browser "
            f"fetch() reader can validate VAME"
        )


# ----- T-5 -----

def test_t_pub_noauth_5_algorithm_manifest_carries_frozen_tags():
    src = (ROOT / "bridge" / "vapi_bridge" / "public_forensic_api.py").read_text()
    # Every FROZEN-v1 tag the plan enumerated MUST appear in the
    # manifest source. This prevents drift between the plan and what
    # the public viewer surfaces.
    for tag in [
        "VAPI-GIC-GENESIS-v1",
        "VAPI-MLGA-SESSION-v1",
        "VAPI-WEC-GENESIS-v1",
        "VAPI-VAME-v1",
        "VAPI-CORPUS-SNAPSHOT-v1",
        "VAPI-CONSENT-v1",
        "VAPI-BIOMETRIC-SNAPSHOT-v1",
        "VAPI-LISTING-v1",
        "VAPI-FRR-v1",
        "VAPI-ZKBA-ARTIFACT-v1",
        "VAPI-AGENT-COMMIT-v1",
        "VAPI-PHYSICAL-DATA-ATTESTATION-v1",
        "VAPI-BT-WITNESS-v1",
        "VAPI-CEDAR-BUNDLE-v1",
    ]:
        assert tag in src, f"FROZEN-v1 tag missing from manifest: {tag}"
