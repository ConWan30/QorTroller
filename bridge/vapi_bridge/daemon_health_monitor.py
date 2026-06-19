"""Standing protocol health monitor — pure-function probes (D-DAEMON-2).

Composes existing sensor patterns: module is pure (no network/subprocess);
runner scripts or daemon idle loop inject live values via dataclasses.

Findings are proposal-only — daemon surfaces drift, operator commits fixes.

F-FW-2 (device_id canon): when ``wiki/methodology/DEVICE_ID_CANON_v1.md`` exists,
CRITICAL fires only on canonical-layer drift (bridge/chain/controller). Documented
firmware outliers in the canon supersession table surface as F-FW-2-DRIFT (MEDIUM)
every run until Phase 1B aligns firmware to keccak256(pubkey).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence

DEVICE_ID_CANON_REL = "wiki/methodology/DEVICE_ID_CANON_v1.md"
CANONICAL_LAYER_RELPATHS = (
    "bridge/vapi_bridge/codec.py",
    "contracts/contracts/DeviceRegistry.sol",
    "controller/persistent_identity.py",
)
FIRMWARE_OUTLIER_RELPATHS = (
    "bridge/firmware/joypad-os/src/qortroller/atca_signer.c",
    "docs/path-a-arc2-prompt.md",
)
_SUPERSEDED_DEVICE_ID_PATTERNS = (
    re.compile(r"SHA-256\s*\(\s*pubkey\s*\|\|\s*serial", re.I),
    re.compile(r"SHA-256\s*\(\s*pubkey_64B\s*\|\|\s*serial", re.I),
    re.compile(r'"atecc-"\s*\+\s*serial', re.I),
)
_KECCAK_DEVICE_ID_PATTERN = re.compile(r"keccak256?\s*\(\s*pubkey", re.I)
_LEGACY_SHA_PATTERN = re.compile(r"SHA-256\s*\(\s*pubkey\s*\|\|\s*serial", re.I)
_LEGACY_KECCAK_PATTERN = re.compile(r"keccak256\s*\(\s*pubkey", re.I)


class HealthSeverity(str, Enum):
    INFO = "INFO"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class HealthState(str, Enum):
    ALIGNED = "ALIGNED"
    DRIFTED = "DRIFTED"
    STALLED = "STALLED"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True)
class HealthFinding:
    probe_id: str
    state: HealthState
    severity: HealthSeverity
    evidence: str
    proposed_action: str = ""


@dataclass(frozen=True)
class HealthMonitorInput:
    """Injected live values — runner fills, module consumes."""

    gic_hours_since_last_link: Optional[float] = None
    gic_stall_threshold_hours: float = 24.0
    claude_md_drift_count: int = 0
    frozen_ref_violation_count: int = 0
    invariant_count_live: Optional[int] = None
    invariant_count_baseline: int = 176
    wallet_drift_iotx: Optional[float] = None
    wallet_drift_tolerance_iotx: float = 0.5
    device_id_formula_conflict: bool = False
    device_id_firmware_drift: bool = False
    ca_backup_disclosure_missing: bool = False


def detect_device_id_formula_conflict(repo_root: Path) -> bool:
    """F-FW-2: True when device_id encoding drifts from adjudicated canon.

    Pre-canon (no DEVICE_ID_CANON_v1.md): legacy rule — both SHA-256(pubkey||serial)
    and keccak256(pubkey) mentions anywhere in .md/.py/.sol → conflict.

    Post-canon: CRITICAL only if canonical layer (codec, DeviceRegistry.sol,
    persistent_identity) lacks keccak256(pubkey) or embeds a superseded formula.
    Firmware outliers documented in the canon supersession table are Phase 1B
    work and do not alone trigger this probe.
    """
    repo_root = Path(repo_root)
    canon = repo_root / DEVICE_ID_CANON_REL
    if not canon.is_file():
        hits_sha = hits_keccak = 0
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
            for fn in files:
                if not fn.endswith((".md", ".py", ".sol")):
                    continue
                try:
                    text = (Path(root) / fn).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if _LEGACY_SHA_PATTERN.search(text):
                    hits_sha += 1
                if _LEGACY_KECCAK_PATTERN.search(text):
                    hits_keccak += 1
        return hits_sha > 0 and hits_keccak > 0

    for rel in CANONICAL_LAYER_RELPATHS:
        path = repo_root / rel
        if not path.is_file():
            return True
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return True
        if not _KECCAK_DEVICE_ID_PATTERN.search(text):
            return True
        for pat in _SUPERSEDED_DEVICE_ID_PATTERNS:
            if pat.search(text):
                return True
    return False


def detect_device_id_firmware_drift(repo_root: Path) -> bool:
    """F-FW-2-DRIFT: True when canon exists and a documented firmware outlier still
    embeds a superseded device_id formula (e.g. atca_signer.c SHA-256(pubkey||serial)).

    Keeps the firmware seam in scope at MEDIUM until Phase 1B rewrites it to keccak.
    """
    repo_root = Path(repo_root)
    canon = repo_root / DEVICE_ID_CANON_REL
    if not canon.is_file():
        return False
    for rel in FIRMWARE_OUTLIER_RELPATHS:
        path = repo_root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in _SUPERSEDED_DEVICE_ID_PATTERNS:
            if pat.search(text):
                return True
    return False


def probe_gic_stall(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if inp.gic_hours_since_last_link is None:
        return HealthFinding(
            "GIC-STALL", HealthState.UNVERIFIABLE, HealthSeverity.INFO,
            "GIC chain age unavailable",
        )
    if inp.gic_hours_since_last_link > inp.gic_stall_threshold_hours:
        return HealthFinding(
            "GIC-STALL", HealthState.STALLED, HealthSeverity.HIGH,
            f"GIC chain stalled {inp.gic_hours_since_last_link:.1f}h "
            f"(threshold {inp.gic_stall_threshold_hours}h)",
            "Investigate bridge watchdog / grind session; propose stream if broken.",
        )
    return None


def probe_claude_drift(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if inp.claude_md_drift_count <= 0:
        return None
    return HealthFinding(
        "CLAUDE-DRIFT", HealthState.DRIFTED, HealthSeverity.MEDIUM,
        f"Sensor A live drift: {inp.claude_md_drift_count} probe(s) DRIFTED",
        "Update CLAUDE.md anchors or reconcile live state.",
    )


def probe_frozen_refs(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if inp.frozen_ref_violation_count <= 0:
        return None
    return HealthFinding(
        "FROZEN-REF", HealthState.DRIFTED, HealthSeverity.HIGH,
        f"{inp.frozen_ref_violation_count} FROZEN-v1 reference(s) in non-FROZEN files",
        "Run mythos frozen_drift variant; propose fixes via ceremony.",
    )


def probe_invariant_count(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if inp.invariant_count_live is None:
        return HealthFinding(
            "INV-COUNT", HealthState.UNVERIFIABLE, HealthSeverity.INFO,
            "Invariant gate count unavailable",
        )
    if inp.invariant_count_live != inp.invariant_count_baseline:
        return HealthFinding(
            "INV-COUNT", HealthState.DRIFTED, HealthSeverity.HIGH,
            f"Live invariant count {inp.invariant_count_live} != "
            f"baseline {inp.invariant_count_baseline}",
            "Reconcile PV-CI baseline before grant artifacts.",
        )
    return None


def probe_wallet_drift(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if inp.wallet_drift_iotx is None:
        return None
    if abs(inp.wallet_drift_iotx) > inp.wallet_drift_tolerance_iotx:
        return HealthFinding(
            "WALLET-DRIFT", HealthState.DRIFTED, HealthSeverity.MEDIUM,
            f"Wallet drift {inp.wallet_drift_iotx:.3f} IOTX "
            f"(tolerance {inp.wallet_drift_tolerance_iotx})",
            "Update CLAUDE.md SENSOR-A-LIVE P-WALLET anchor.",
        )
    return None


def probe_device_id_conflict(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if not inp.device_id_formula_conflict:
        return None
    return HealthFinding(
        "F-FW-2", HealthState.DRIFTED, HealthSeverity.CRITICAL,
        "device_id canonical-layer drift vs DEVICE_ID_CANON_v1 "
        "(keccak256(65B SEC1 0x04‖X‖Y); see wiki/methodology/DEVICE_ID_CANON_v1.md)",
        "OPERATOR-ACTION: align codec/chain/controller to canon.",
    )


def probe_device_id_firmware_drift(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if not inp.device_id_firmware_drift:
        return None
    return HealthFinding(
        "F-FW-2-DRIFT", HealthState.DRIFTED, HealthSeverity.MEDIUM,
        "atca_signer.c device_id formula diverges from DEVICE_ID_CANON_v1 "
        "(SHA-256(pubkey‖serial) vs keccak256(65B SEC1 pubkey); "
        "see wiki/methodology/DEVICE_ID_CANON_v1.md §3)",
        "Phase 1B: rewrite atca_signer.c to F-KEY-1 slot-read + provisioning-time keccak.",
    )


def probe_ca_backup(inp: HealthMonitorInput) -> Optional[HealthFinding]:
    if not inp.ca_backup_disclosure_missing:
        return None
    return HealthFinding(
        "OA-1", HealthState.DRIFTED, HealthSeverity.HIGH,
        "MFG Root CA backup disclosure trail incomplete (F-DECON-3.2)",
        "OPERATOR-ACTION: back up ~/.vapi/qortroller_foundation_mfg_ca.json",
    )


_ALL_PROBES = (
    probe_gic_stall,
    probe_claude_drift,
    probe_frozen_refs,
    probe_invariant_count,
    probe_wallet_drift,
    probe_device_id_conflict,
    probe_device_id_firmware_drift,
    probe_ca_backup,
)


def run_health_monitor(inp: HealthMonitorInput) -> List[HealthFinding]:
    """Run all probes; return non-None findings sorted by severity."""
    findings: List[HealthFinding] = []
    for probe in _ALL_PROBES:
        f = probe(inp)
        if f is not None:
            findings.append(f)
    sev_order = {
        HealthSeverity.CRITICAL: 0,
        HealthSeverity.HIGH: 1,
        HealthSeverity.MEDIUM: 2,
        HealthSeverity.INFO: 3,
    }
    findings.sort(key=lambda x: sev_order.get(x.severity, 99))
    return findings


def format_findings_markdown(findings: Sequence[HealthFinding]) -> str:
    if not findings:
        return "All health probes ALIGNED (no findings)."
    lines = ["# Daemon Health Monitor Findings", ""]
    for f in findings:
        lines.append(f"## [{f.severity.value}] {f.probe_id} — {f.state.value}")
        lines.append(f"- **Evidence:** {f.evidence}")
        if f.proposed_action:
            lines.append(f"- **Proposed action:** {f.proposed_action}")
        lines.append("")
    return "\n".join(lines)
