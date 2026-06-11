"""HWFL-1 Sensor C v0.1 — Rung-gate readiness ledger.

Standalone module (NOT a Mythos variant — D-HWFL-7) producing a
machine-checkable snapshot of every gate across Rungs 1-4 of the
QorTroller manufacturing staircase, rendered honestly: nothing
LIVE-weighted that isn't live, dormant items flagged, hardware-gated
items marked as such.

Output artifacts:
  - audits/rung-gate-ledger-cycle-<N>-<YYYY-MM-DD>.md  (per-cycle audit)
  - audits/rung-gate-ledger-latest.json                (machine-readable,
                                                        consumable by
                                                        vapi_unified_state
                                                        once MCP wiring
                                                        lands in v0.2)

State taxonomy (FROZEN for v0.1 — taxonomy edits require a cycle decision):
  LIVE                  — gate met now; verifier returned True against repo state
  DORMANT               — work hasn't started but isn't blocked
  HARDWARE-GATED        — needs operator-confirmed hardware (no software path)
  BLOCKED-ON-SENSOR-B   — needs supply/standards watch data Sensor B will emit
  BLOCKED-ON-EXTERNAL   — third-party gate (e.g. IIP-64 PR movement)
  DEFERRED              — explicit scope-out
  UNVERIFIABLE          — verifier raised or returned indeterminate; fail-open
                          posture (NEVER converts UNVERIFIABLE -> LIVE)

Honesty rails:
  - Verifier exception => UNVERIFIABLE, never LIVE. Cycle artifact records why.
  - HARDWARE-GATED gates have no verifier — state is intrinsic; operator
    confirms via separate ceremony, not via Sensor C.
  - Gate list is FROZEN per cycle (no dynamic discovery); externalization
    + amendment is a v0.2 cycle decision.
  - Sensor C v0.1 does NOT model durability/fragility of LIVE gates (e.g.
    G1.6 MFG CA is LIVE-by-existence but single-copy per F-DECON-3.2).
    LIVE-FRAGILE state deferred to v0.2 per D-HWFL-9.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable


class GateState(str, Enum):
    LIVE = "LIVE"
    DORMANT = "DORMANT"
    HARDWARE_GATED = "HARDWARE-GATED"
    BLOCKED_ON_SENSOR_B = "BLOCKED-ON-SENSOR-B"
    BLOCKED_ON_EXTERNAL = "BLOCKED-ON-EXTERNAL"
    DEFERRED = "DEFERRED"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True, slots=True)
class GateDef:
    """Static gate definition — frozen at module load."""
    rung: int
    gate_id: str          # "G1.4", "G2.7", etc.
    name: str
    intrinsic_state: GateState | None   # None => has verifier; else => state is intrinsic
    verifier_name: str | None = None
    spec_ref: str = ""    # docs ref / CLAUDE.md section / external URL


@dataclass(slots=True)
class GateResult:
    """Per-cycle resolution of a gate."""
    gate: GateDef
    state: GateState
    evidence: str         # what made the verifier pass/fail; or static note for intrinsic
    verified_at: str      # ISO-8601 UTC

    def to_dict(self) -> dict:
        return {
            "rung": self.gate.rung,
            "gate_id": self.gate.gate_id,
            "name": self.gate.name,
            "state": self.state.value,
            "evidence": self.evidence,
            "verified_at": self.verified_at,
            "spec_ref": self.gate.spec_ref,
        }


# ---------------------------------------------------------------------------
# Verifier functions for LIVE-candidate gates (G1.4-G1.7).
# Each returns (state, evidence). Exceptions caught at assemble layer => UNVERIFIABLE.
# ---------------------------------------------------------------------------

def _verify_g1_4_vmdr_deployed(repo_root: Path) -> tuple[GateState, str]:
    """VAPIManufacturerDeviceRegistry deployed on IoTeX testnet."""
    addr_file = repo_root / "contracts" / "deployed-addresses.json"
    if not addr_file.exists():
        return GateState.UNVERIFIABLE, "contracts/deployed-addresses.json missing"
    data = json.loads(addr_file.read_text(encoding="utf-8"))
    addr = data.get("VAPIManufacturerDeviceRegistry")
    if not addr:
        return GateState.UNVERIFIABLE, "VAPIManufacturerDeviceRegistry key absent"
    if not isinstance(addr, str) or not addr.startswith("0x") or len(addr) != 42:
        return GateState.UNVERIFIABLE, f"malformed address: {addr!r}"
    return GateState.LIVE, f"VMDR @ {addr} (IoTeX testnet chainId 4690)"


def _verify_g1_5_reference_device_registered(repo_root: Path) -> tuple[GateState, str]:
    """First reference device registered on-chain (CLAUDE.md tx anchor)."""
    claude_md = repo_root / "CLAUDE.md"
    if not claude_md.exists():
        return GateState.UNVERIFIABLE, "CLAUDE.md missing"
    text = claude_md.read_text(encoding="utf-8", errors="ignore")
    # The Path A Arc 1 commit anchors the first device registration tx.
    if "0x68f6cf49564ed2b193d00e881e5cc9488111a8bc05951c2f2af55e25050ac9c0" in text:
        return (
            GateState.LIVE,
            "registration tx 0x68f6cf49…ac9c0 cited in CLAUDE.md (block 44028531)",
        )
    return GateState.UNVERIFIABLE, "reference-device tx anchor not found in CLAUDE.md"


def _verify_g1_6_mfg_ca_file_present(repo_root: Path) -> tuple[GateState, str]:
    """ManufacturerRootCA file at canonical path (~/.vapi/qortroller_foundation_mfg_ca.json).
    Checks existence only — does NOT read contents (key material)."""
    ca_path = Path.home() / ".vapi" / "qortroller_foundation_mfg_ca.json"
    if ca_path.exists():
        return (
            GateState.LIVE,
            "~/.vapi/qortroller_foundation_mfg_ca.json present "
            "(SINGLE-COPY per F-DECON-3.2 — see OA-1 in OPERATOR-ACTION box)",
        )
    return GateState.UNVERIFIABLE, f"{ca_path} not found"


def _verify_g1_7_secure_element_honesty_rail(repo_root: Path) -> tuple[GateState, str]:
    """SecureElementBackend raises NotImplementedError until Arc 2 wires real silicon."""
    se_path = repo_root / "bridge" / "vapi_bridge" / "signing_backends" / "secure_element.py"
    if not se_path.exists():
        return GateState.UNVERIFIABLE, "signing_backends/secure_element.py missing"
    text = se_path.read_text(encoding="utf-8", errors="ignore")
    if "NotImplementedError" not in text:
        return (
            GateState.UNVERIFIABLE,
            "NotImplementedError marker absent — honesty rail may have been removed",
        )
    return (
        GateState.LIVE,
        "SecureElementBackend raises NotImplementedError "
        "(blocks silent host-key fallback; Arc 2 hardware-gated)",
    )


_VERIFIERS: dict[str, Callable[[Path], tuple[GateState, str]]] = {
    "verify_g1_4_vmdr_deployed":            _verify_g1_4_vmdr_deployed,
    "verify_g1_5_reference_device":         _verify_g1_5_reference_device_registered,
    "verify_g1_6_mfg_ca_present":           _verify_g1_6_mfg_ca_file_present,
    "verify_g1_7_secure_element_honesty":   _verify_g1_7_secure_element_honesty_rail,
}


# ---------------------------------------------------------------------------
# Canonical gate registry — FROZEN per cycle (D-HWFL-8 confirmed 22-gate list).
# Externalization (e.g. YAML) deferred to v0.2.
# ---------------------------------------------------------------------------
_CANONICAL_GATES: tuple[GateDef, ...] = (
    # RUNG 1 — reference rig
    GateDef(1, "G1.1", "DualSense Edge physically connected",
            GateState.HARDWARE_GATED, None,
            "master prompt RUNG 1; operator ceremony"),
    GateDef(1, "G1.2", "ATECC608A breakout physically connected",
            GateState.HARDWARE_GATED, None,
            "master prompt RUNG 1; Arc 2 hardware gate"),
    GateDef(1, "G1.3", "CH341A USB-I2C bridge present",
            GateState.HARDWARE_GATED, None,
            "docs/path-a-manufacturing-spec.md §2 Recommended host adapter"),
    GateDef(1, "G1.4", "VAPIManufacturerDeviceRegistry deployed on IoTeX testnet",
            None, "verify_g1_4_vmdr_deployed",
            "docs/path-a-manufacturing-spec.md §1 + §6.3"),
    GateDef(1, "G1.5", "First reference device registered on-chain",
            None, "verify_g1_5_reference_device",
            "CLAUDE.md Path A Arc 1 — tx 0x68f6cf49… block 44028531"),
    GateDef(1, "G1.6", "ManufacturerRootCA file present at canonical path",
            None, "verify_g1_6_mfg_ca_present",
            "docs/path-a-manufacturing-spec.md §1 reference-impl honesty stamp"),
    GateDef(1, "G1.7", "SecureElementBackend honesty rail intact",
            None, "verify_g1_7_secure_element_honesty",
            "Path A Arc 1 SecureElementBackend stub (raises NotImplementedError)"),

    # RUNG 2 — dev kit (software-side work in scope; physical build = operator ceremony)
    GateDef(2, "G2.1", "Dev-kit BOM document exists (two suppliers per critical part)",
            GateState.DORMANT, None,
            "master prompt RUNG 2 — known early-cycle candidate"),
    GateDef(2, "G2.2", "Zephyr firmware target for QorTroller controller",
            GateState.DORMANT, None,
            "Sensor A B1: only pebble_tracker.overlay exists today"),
    GateDef(2, "G2.3", "Thread-C-equivalent isolation statement in firmware spec",
            GateState.DORMANT, None,
            "master prompt RUNG 2 — Zephyr work-queue / priority-ceiling thread"),
    GateDef(2, "G2.4", "φ sanitization device-residency design",
            GateState.DORMANT, None,
            "Sensor A B2: φ host-side; wiki/methodology/sensor_stack_v2_1*"),
    GateDef(2, "G2.5", "Hall/TMR stick module selection finalized",
            GateState.DORMANT, None,
            "Sensor Stack v2.1 — 3 candidates (K-Silver JH16, MIDAS 5-pin, Magneto TMR)"),
    GateDef(2, "G2.6", "IMU module selection finalized",
            GateState.DORMANT, None,
            "master prompt RUNG 2 — Sensor Stack v2.1 #1/#4 measurement gates"),
    GateDef(2, "G2.7", "ESP32-class module cert status known",
            GateState.BLOCKED_ON_SENSOR_B, None,
            "Sensor B watch surface (not yet built — Cycle 3 per D-HWFL-1)"),

    # RUNG 3 — ODM partner (evidence prep, all DORMANT)
    GateDef(3, "G3.1", "Partner-handoff package assembler",
            GateState.DORMANT, None,
            "master prompt RUNG 3 — assembles spec + parity evidence + BOM + birth-cert runbook"),
    GateDef(3, "G3.2", "TrustFLEX provisioning path amendment to spec",
            GateState.DORMANT, None,
            "docs/path-a-manufacturing-spec.md §3 + §8 partner ceremony"),
    GateDef(3, "G3.3", "Manufacturer CA chained to reference root — design",
            GateState.DORMANT, None,
            "docs/path-a-manufacturing-spec.md §1 partner-redeploy model"),
    GateDef(3, "G3.4", "Per-batch slot-config audit checklist",
            GateState.DORMANT, None,
            "docs/path-a-manufacturing-spec.md §8.2"),
    GateDef(3, "G3.5", "Two-supplier cost model for critical parts",
            GateState.DORMANT, None,
            "master prompt RUNG 3"),

    # RUNG 4 — licensed manufacturer standard
    GateDef(4, "G4.1", "IIP-64 PR #72 movement / merge",
            GateState.BLOCKED_ON_EXTERNAL, None,
            "github.com/iotexproject/iips/pull/72 — operator-tracked"),
    GateDef(4, "G4.2", "Spec-as-compliance-standard formalized",
            GateState.DORMANT, None,
            "master prompt RUNG 4"),
    GateDef(4, "G4.3", "Device-identity registry interop spec",
            GateState.DORMANT, None,
            "IIP-64-aligned; gated on G4.1"),
)


# ---------------------------------------------------------------------------
# Ledger assembly
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RungLedger:
    """Per-cycle snapshot of all 22 gates."""
    cycle: int
    cycle_date: str          # YYYY-MM-DD
    generated_at: str        # ISO-8601 UTC
    results: list[GateResult]

    def state_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.state.value] = counts.get(r.state.value, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "schema_version": "vapi-rung-gate-ledger-v1",
            "cycle": self.cycle,
            "cycle_date": self.cycle_date,
            "generated_at": self.generated_at,
            "gate_count": len(self.results),
            "state_counts": self.state_counts(),
            "gates": [r.to_dict() for r in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=False)

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Sensor C — Rung-Gate Readiness Ledger (Cycle {self.cycle}, {self.cycle_date})\n")
        lines.append(
            "HWFL-1 Sensor C v0.1 — machine-checkable snapshot of every gate "
            "across Rungs 1-4 of the QorTroller manufacturing staircase. "
            "Honest weighting: nothing LIVE that isn't verifiable now. "
            f"Generated `{self.generated_at}` by `scripts/run_sensor_c.py`. "
            "Machine-readable companion: `audits/rung-gate-ledger-latest.json`.\n"
        )

        # Standing OPERATOR-ACTION box (R4 / nag-once-per-cycle).
        lines.append("\n## Standing OPERATOR-ACTION box (loop never auto-touches)\n")
        lines.append("- [ ] **OA-1** Back up `~/.vapi/qortroller_foundation_mfg_ca.json` (517 B) — F-DECON-3.2 interim. Highest-leverage 5-min action.")
        lines.append("- [ ] **OA-2** Create `docs/disaster-recovery-runbook.private.md` with full AWS KMS ARNs.")
        lines.append("- [ ] **OA-3** IAM scope-down on bridge/.env AWS keys → `KMS:Sign` + `KMS:GetPublicKey` on the two specific key ARNs.")
        lines.append("- [ ] **OA-4** Long-term: HSM-backed ManufacturerRootCA + device re-issuance.")
        lines.append("")

        counts = self.state_counts()
        lines.append("\n## State summary\n")
        lines.append("| State | Count |")
        lines.append("|---|---|")
        for state in GateState:
            n = counts.get(state.value, 0)
            if n:
                lines.append(f"| {state.value} | {n} |")
        lines.append(f"| **Total** | **{len(self.results)}** |")
        lines.append("")

        # Per-rung tables.
        rungs = sorted({r.gate.rung for r in self.results})
        for rung in rungs:
            lines.append(f"\n## Rung {rung}\n")
            lines.append("| Gate | Name | State | Evidence |")
            lines.append("|---|---|---|---|")
            for r in (gr for gr in self.results if gr.gate.rung == rung):
                ev = r.evidence.replace("|", "\\|")
                lines.append(f"| `{r.gate.gate_id}` | {r.gate.name} | `{r.state.value}` | {ev} |")
            lines.append("")

        lines.append("\n## Provenance\n")
        lines.append(f"- Canonical gate registry: `bridge/vapi_bridge/sensor_c_rung_ledger.py::_CANONICAL_GATES` ({len(self.results)} gates, FROZEN per cycle)")
        lines.append(f"- Verifier functions: `bridge/vapi_bridge/sensor_c_rung_ledger.py::_VERIFIERS` ({len(_VERIFIERS)} active)")
        lines.append("- Schema: `vapi-rung-gate-ledger-v1` (JSON companion artifact)")
        lines.append("- Rung definitions: HWFL-1 master prompt + `docs/path-a-manufacturing-spec.md`")

        return "\n".join(lines) + "\n"


def assemble_ledger(repo_root: Path, *, cycle: int, cycle_date: str | None = None) -> RungLedger:
    """Run all verifiers and produce the cycle snapshot. Fail-open: verifier
    exceptions => UNVERIFIABLE, never LIVE."""
    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    date = cycle_date or now_utc[:10]
    results: list[GateResult] = []

    for gate in _CANONICAL_GATES:
        if gate.intrinsic_state is not None:
            results.append(GateResult(
                gate=gate,
                state=gate.intrinsic_state,
                evidence=f"intrinsic state ({gate.intrinsic_state.value}); see spec_ref",
                verified_at=now_utc,
            ))
            continue

        verifier = _VERIFIERS.get(gate.verifier_name or "")
        if verifier is None:
            results.append(GateResult(
                gate=gate,
                state=GateState.UNVERIFIABLE,
                evidence=f"verifier {gate.verifier_name!r} not registered",
                verified_at=now_utc,
            ))
            continue

        try:
            state, evidence = verifier(repo_root)
        except Exception as exc:  # noqa: BLE001 — fail-open per honesty rail
            state, evidence = GateState.UNVERIFIABLE, f"verifier raised: {exc!r}"
        results.append(GateResult(
            gate=gate, state=state, evidence=evidence, verified_at=now_utc,
        ))

    return RungLedger(
        cycle=cycle,
        cycle_date=date,
        generated_at=now_utc,
        results=results,
    )


def canonical_gate_count() -> int:
    """Exposed for tests + audit assertions. v0.1 = 22."""
    return len(_CANONICAL_GATES)
