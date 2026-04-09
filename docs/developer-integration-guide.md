# VAPI Developer Integration Guide

**Phase 106 — Game Developer Integration Layer**

This guide covers integrating VAPI tournament eligibility checking into your game backend.

---

## Overview

VAPI provides cryptographically verifiable proof of human presence in competitive gaming.
The single composable gate is `VAPIProtocolLens.isFullyEligible()` on IoTeX L1.
From Python, the SDK exposes the same logic through simple HTTP calls.

---

## Install

```bash
# SDK is a single file — no package manager needed
cp sdk/vapi_sdk.py your_project/
```

Requirements: Python 3.11+, no external dependencies (uses stdlib `urllib.request`).

---

## Quickstart — Tournament Eligibility

```python
from vapi_sdk import VAPITournamentIntegration

integration = VAPITournamentIntegration(
    base_url="http://your-bridge-host:8080",
    api_key="your-operator-api-key"
)

result = integration.request_game_demo(
    device_id="device_abc123",
    wallet="0xYourPlayerWallet"
)

if result.entered:
    print("Player is eligible — allow tournament entry")
else:
    print(f"Player not eligible: {result.error}")
```

`request_game_demo()` never raises. It returns a `TournamentEntryResult` with:

| Field | Type | Description |
|-------|------|-------------|
| `device_id` | str | Input device identifier |
| `wallet` | str | Player wallet address |
| `entered` | bool | True if eligible AND has valid VHP |
| `demo_mode` | bool | Always True (see disclosure below) |
| `is_eligible` | bool | Protocol eligibility check passed |
| `has_valid_vhp` | bool | Non-expired VHP soulbound token exists |
| `error` | str\|None | Error message or None on success |

---

## Player Eligibility Check (Direct)

For lower-level control:

```python
from vapi_sdk import VAPITournamentClient

client = VAPITournamentClient(
    base_url="http://your-bridge-host:8080",
    api_key="your-operator-api-key"
)

eligibility = client.check_player(device_id="device_abc123", wallet="0x...")
print(f"eligible: {eligibility.is_eligible}")
print(f"consecutive_clean: {eligibility.consecutive_clean}")
print(f"cert_level: {eligibility.cert_level}")
print(f"expires_at: {eligibility.expires_at}")
```

---

## Machine-Verifiable Readiness

Query the live mode readiness gate to verify the operator backend state:

```python
from vapi_sdk import VAPILiveModeValidator

validator = VAPILiveModeValidator(
    base_url="http://your-bridge-host:8080",
    api_key="your-operator-api-key"
)

report = validator.get_latest()
print(f"ready_for_live: {report.ready_for_live}")
print(f"n_tested: {report.n_tested}")
print(f"false_positive_rate: {report.false_positive_rate}")
```

You can also trigger a fresh validation:

```python
result = validator.run_validation(n=100)
print(f"ready_for_live: {result.ready_for_live}")
```

---

## Honest Disclosure

VAPI is in **pre-calibration deployment**. The following limitations apply:

| Metric | Current Value | Target |
|--------|--------------|--------|
| Inter-person separation ratio | **1.261** (Phase 143, N=11 touchpad_corners; classification 63.6% — BLOCKER until ≥80%) | > 1.0 |
| `demo_mode` | `True` | `False` (post-calibration) |
| `ready_for_live` | Software-only gate | Hardware-calibrated |

The `ready_for_live` field from `/agent/live-mode-readiness` is machine-verifiable and
reflects the software preconditions only. Tournament deployment additionally requires
separation ratio > 1.0 confirmed with real calibration hardware.

Until then: use `demo_mode=True` for development integration and testing. The protocol
architecture, agent fleet, and on-chain infrastructure are fully production-ready.

---

## On-Chain Verification

The composable tournament gate is available on IoTeX Testnet (chain ID 4690):

```
VAPIProtocolLens.isFullyEligible(deviceIdHash) → bool
Address: 0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf
```

See `contracts/deployed-addresses.json` for all 38 contract addresses.
