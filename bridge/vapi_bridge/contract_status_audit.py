"""HWFL-1 contract-status audit module — F-CYCLE10-1 Option (b) closure.

Cycle 11 closed F-CYCLE10-1 Option (a) blunt: prose 49 → 66 +
anchor bump. Option (b) (active-vs-superseded classification) was
deferred. Cycle 15 picks it up: pure-function classifier over
deployed-addresses.json's addr-shaped keys + supersession meta-keys.

Classification rules (FROZEN for v0.1):
  1. Address-shaped key with `_superseded` substring => SUPERSEDED
     (explicit marker in the key itself)
  2. Address-shaped key whose matching meta-key has a
     `_superseded_note` entry => SUPERSEDED (explicit meta marker)
  3. Address-shaped key with name=`X` AND sibling=`XV2`/`X_v2`/
     `XV3` exists AND no explicit ACTIVE marker on the bare name
     => DEPRECATED-INFERRED (versioning pattern likely-superseded
     but NOT explicitly marked)
  4. Default => ACTIVE

Honesty rails:
  - DEPRECATED-INFERRED is a heuristic, not a fact. The auditor
    surfaces the inference; operator confirms by checking actual
    contract wiring (which contract address is the .env/SDK
    actively pointing at, which is referenced by chain.py, etc.).
  - The classifier never reads chain state or contracts source —
    purely metadata-driven. A future v0.2 could cross-check
    contracts/.env / chain.py imports for higher confidence.
  - Pure-function module. Runner-side reads the JSON, classifier
    consumes the parsed dict.

Output:
  - ContractStatusReport (immutable dataclass)
  - to_markdown() audit artifact
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple


class ContractStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"            # Explicit marker (key suffix or meta-note)
    DEPRECATED_INFERRED = "DEPRECATED-INFERRED"  # Versioning heuristic; not explicit
    UNKNOWN = "UNKNOWN"                  # Fallback; should never appear unless rules change


@dataclass(frozen=True)
class ContractRecord:
    key: str
    address: str
    status: ContractStatus
    reason: str
    superseded_by: Optional[str] = None  # If known, which sibling supersedes


@dataclass(frozen=True)
class ContractStatusReport:
    ts_iso: str
    total: int
    active_count: int
    superseded_count: int
    deprecated_inferred_count: int
    unknown_count: int
    records: Tuple[ContractRecord, ...]

    def to_markdown(self) -> str:
        rows = []
        rows.append("# QorTroller contract-status audit — F-CYCLE10-1 Option (b)")
        rows.append("")
        rows.append(f"- Timestamp: `{_esc(self.ts_iso)}`")
        rows.append(f"- Total addr-shaped non-meta keys: {self.total}")
        rows.append(f"- ACTIVE: {self.active_count}")
        rows.append(f"- SUPERSEDED (explicit): {self.superseded_count}")
        rows.append(f"- DEPRECATED-INFERRED (versioning heuristic): {self.deprecated_inferred_count}")
        if self.unknown_count:
            rows.append(f"- UNKNOWN: {self.unknown_count}")
        rows.append("")
        rows.append("## Non-ACTIVE records (the interesting ones)")
        rows.append("")
        non_active = [r for r in self.records if r.status != ContractStatus.ACTIVE]
        if not non_active:
            rows.append("_(none — all addresses ACTIVE)_")
        else:
            rows.append("| Key | Address | Status | Reason | Superseded by |")
            rows.append("|-----|---------|--------|--------|---------------|")
            for r in non_active:
                rows.append(
                    "| {key} | `{addr}` | {status} | {reason} | {by} |".format(
                        key=_esc(r.key),
                        addr=_esc(r.address),
                        status=r.status.value,
                        reason=_esc(r.reason),
                        by=_esc(r.superseded_by or "—"),
                    )
                )
        rows.append("")
        rows.append("## All ACTIVE keys")
        rows.append("")
        rows.append("| Key | Address |")
        rows.append("|-----|---------|")
        for r in self.records:
            if r.status == ContractStatus.ACTIVE:
                rows.append(f"| {_esc(r.key)} | `{_esc(r.address)}` |")
        rows.append("")
        rows.append("## Honesty rail")
        rows.append("")
        rows.append(
            "DEPRECATED-INFERRED is a versioning heuristic, NOT a fact. "
            "Operator confirms by checking actual contract wiring "
            "(bridge/.env, chain.py imports, SDK consumers). A future "
            "v0.2 of this auditor could cross-check those sources for "
            "higher confidence."
        )
        rows.append("")
        return "\n".join(rows)


# Regex matches `<contractname>_superseded_note` or `<contractname>_superseded` meta-key bodies
_SUPERSEDED_META_RE = re.compile(r"^_(?P<name>[A-Za-z][A-Za-z0-9]*)_superseded(?:_note)?$")

# Matches an optional trailing version token: `V2`, `V3`, `_v2`, `_v4`, ...
# Group `base` is the name without the version; `num` is the integer version.
# A bare name (no version token) is treated as version 1.
_VERSION_TOKEN_RE = re.compile(r"^(?P<base>.*?)(?:V|_v)(?P<num>\d+)$")


def _version_of(name: str) -> Tuple[str, int]:
    """Return (base_name, version_int). Bare names are version 1.

    Examples:
      TournamentGate     -> ("TournamentGate", 1)
      TournamentGateV2   -> ("TournamentGate", 2)
      VAPIProtocolLens_v2-> ("VAPIProtocolLens", 2)
    """
    m = _VERSION_TOKEN_RE.match(name)
    if m and m.group("base"):
        return m.group("base"), int(m.group("num"))
    return name, 1


def _meta_marked_superseded(meta_keys: Mapping[str, object]) -> Dict[str, str]:
    """Returns map of contract-name-lowercased → meta key path.

    The classifier matches against lowercased contract name because
    meta-key naming is inconsistent (`_VAPIProtocolLens_v1_superseded_note`
    vs `_separationratioregistry_superseded_note` vs
    `_vapioperatoragentnft_correction_2026_05_24`)."""
    out: Dict[str, str] = {}
    for k in meta_keys:
        m = _SUPERSEDED_META_RE.match(k)
        if m:
            out[m.group("name").lower()] = k
    return out


def _has_higher_version_sibling(name: str, all_keys: List[str]) -> Optional[str]:
    """If a sibling key shares `name`'s base but has a higher version,
    return the immediately-next-higher sibling (smallest version > name's).

    `name` and each candidate are decomposed via `_version_of`. A bare
    name (version 1) is superseded by any V2+ sibling; a V2 is
    superseded by a V3; etc. The `_superseded` suffix is excluded from
    sibling candidacy (those are caught by Rule 1 directly)."""
    base, ver = _version_of(name)
    best: Optional[Tuple[int, str]] = None
    for cand in all_keys:
        if cand == name or "_superseded" in cand.lower():
            continue
        cbase, cver = _version_of(cand)
        if cbase == base and cver > ver:
            if best is None or cver < best[0]:
                best = (cver, cand)
    return best[1] if best is not None else None


def audit_contracts(
    deployed: Mapping[str, object],
    ts_iso: Optional[str] = None,
) -> ContractStatusReport:
    """Classify every addr-shaped non-meta key in `deployed`.

    `deployed` is the parsed `contracts/deployed-addresses.json` dict.
    """
    if ts_iso is None:
        ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta_keys = {k: v for k, v in deployed.items() if k.startswith("_")}
    addr_keys: List[Tuple[str, str]] = []
    for k, v in deployed.items():
        if k.startswith("_"):
            continue
        if not isinstance(v, str) or not v.startswith("0x") or len(v) != 42:
            continue
        addr_keys.append((k, v))

    meta_superseded = _meta_marked_superseded(meta_keys)
    all_addr_key_names = [k for k, _ in addr_keys]
    records: List[ContractRecord] = []

    for key, addr in addr_keys:
        # Rule 1: explicit _superseded suffix on the key itself
        if "_superseded" in key.lower():
            records.append(ContractRecord(
                key=key, address=addr,
                status=ContractStatus.SUPERSEDED,
                reason="key contains '_superseded' substring (explicit marker)",
            ))
            continue
        # Rule 2: matching meta-key _<name>_superseded_note
        if key.lower() in meta_superseded:
            records.append(ContractRecord(
                key=key, address=addr,
                status=ContractStatus.SUPERSEDED,
                reason=f"meta-key '{meta_superseded[key.lower()]}' marks supersession",
            ))
            continue
        # Rule 3: versioning heuristic — `X` exists alongside `XV2` etc.
        sibling = _has_higher_version_sibling(key, all_addr_key_names)
        if sibling is not None:
            records.append(ContractRecord(
                key=key, address=addr,
                status=ContractStatus.DEPRECATED_INFERRED,
                reason=f"sibling '{sibling}' exists with higher version suffix (heuristic, not explicit)",
                superseded_by=sibling,
            ))
            continue
        # Rule 4: default ACTIVE
        records.append(ContractRecord(
            key=key, address=addr,
            status=ContractStatus.ACTIVE,
            reason="no supersession marker and no higher-version sibling",
        ))

    active = sum(1 for r in records if r.status == ContractStatus.ACTIVE)
    superseded = sum(1 for r in records if r.status == ContractStatus.SUPERSEDED)
    deprecated = sum(1 for r in records if r.status == ContractStatus.DEPRECATED_INFERRED)
    unknown = sum(1 for r in records if r.status == ContractStatus.UNKNOWN)

    return ContractStatusReport(
        ts_iso=ts_iso,
        total=len(records),
        active_count=active,
        superseded_count=superseded,
        deprecated_inferred_count=deprecated,
        unknown_count=unknown,
        records=tuple(records),
    )


def _esc(s: str) -> str:
    if not s:
        return ""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace("|", "\\|")
         .replace("\n", " ")
    )
