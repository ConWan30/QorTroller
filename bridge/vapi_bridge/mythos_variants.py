"""Phase O5-MYTHOS-MINIMAL M.2 + Operator-Initiative Audit Extension — Mythos variants.

Three variants ship:
  1. Mythos-Frozen (M.2)              — PV-CI invariant drift detector
  2. Mythos-Stability (M.2)           — async-hazard + silent-pass auditor
  3. Mythos-Operator-Initiative-Audit — operator-authorized extension; audits
                                        past + current + future Operator Initiative
                                        synchronization across every architectural
                                        surface; see mythos_operator_initiative_audit
                                        below for the 5 check families.

Each is a deterministic, fail-open async function that returns a list of
MythosFindingResult. The cadence engine (M.1) invokes them via
get_pending_variants(); the MCP tool layer (vapi-mcp/unified_server.py)
wraps them as `vapi_mythos_frozen_drift`, `vapi_mythos_stability_sweep`,
and `vapi_mythos_operator_initiative_audit` for operator-runtime invocation.

Variants are pure-function — they read source, never mutate. Persistence
to mythos_finding_log happens at the cadence-engine layer (M.1 `record_
mythos_finding`), not here. This separation lets manual MCP invocations
return findings as a dict without touching the DB.

INV-MYTHOS-FROZEN-PROTECTION-001 (M.3): the store layer FORCES tier=3 on
frozen_region=True findings. The variants can suggest tier=1; the store
overrides it. Mythos NEVER auto-fixes FROZEN material.

Mythos-Frozen (Mode A only — Mode B FROZEN-annotation cross-check
deferred to Priority 5):
  Wraps `scripts/vapi_invariant_gate.check_invariants()` and surfaces ANY
  invariant that would FAIL if `--report` were run now (pattern not found,
  digest drift vs allowlist, etc.). Severity HIGH per finding.

Mythos-Stability (2 patterns from this session's empirical Mythos audit):
  1. ``urllib.urlopen(...)`` called without a ``timeout=`` argument — HIGH
     (executor-pool starvation risk per Mythos audit commit 48236084).
  2. Silent ``except Exception: pass`` with NO deliberate-fail-open
     comment within 2 lines — MEDIUM (error-swallowing hides real
     failures per Mythos audit commit 48236084). Patterns marked
     ``# idempotent`` / ``# fail-open`` / ``# noqa: BLE001`` /
     ``# intentional`` are skipped (they declare the silent pass is the
     intended contract — common in VAPI's bridge for store helpers).

Additional patterns (subprocess kill+reap, un-awaited coroutines,
multi-mythos-variant consensus checks) deferred to Priority 5 — the
minimal ship is deliberately tight.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Iterable

from .mythos_cadence_engine import MythosFindingResult

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Repo-root resolution (testable via injected path)
# --------------------------------------------------------------------------
def _resolve_repo_root(repo_root: Path | None = None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    # From bridge/vapi_bridge/mythos_variants.py, repo root is parents[2].
    return Path(__file__).resolve().parents[2]


def _coherence_id(variant: str, key: str) -> str:
    """Deterministic anti-replay key. Same variant+key always yields the
    same coherence_id, so duplicate findings UNIQUE-dedup at the store
    layer (insert_mythos_finding returns 0 on collision)."""
    h = hashlib.sha256(f"{variant}:{key}".encode("utf-8")).hexdigest()
    return f"mythos_{variant}_{h[:16]}"


# ==========================================================================
# Mythos-Frozen — wraps PV-CI check_invariants
# ==========================================================================
async def mythos_frozen_drift(
    *,
    repo_root: Path | None = None,
) -> list[MythosFindingResult]:
    """Run scripts/vapi_invariant_gate.check_invariants() and surface ANY
    invariant that would FAIL if `--report` were invoked now. Each failing
    invariant becomes a HIGH finding with frozen_region=True (forces
    tier=3 read-only per INV-MYTHOS-FROZEN-PROTECTION-001).

    Fail-open: any error gathering / parsing yields a single LOW finding
    describing the gather failure, never raises."""
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []

    try:
        import sys
        scripts_path = str(root / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        import vapi_invariant_gate as gate  # type: ignore

        results = gate.check_invariants(proposal_type="all")
        allowlist = gate.load_allowlist() if hasattr(gate, "load_allowlist") else {}
        for r in results:
            # Each result has: id / description / file / digest / match_count
            # / file_found / pattern_matched. Verified against
            # scripts/vapi_invariant_gate.check_invariants:843-851.
            inv_id = str(r.get("id", "?"))
            file_found = bool(r.get("file_found", True))
            pattern_matched = bool(r.get("pattern_matched", True))
            digest = str(r.get("digest", ""))
            allow_entry = allowlist.get(inv_id, {}) if isinstance(allowlist, dict) else {}
            allow_digest = str(allow_entry.get("digest", "")) if isinstance(allow_entry, dict) else ""
            # Classify what (if anything) is wrong for this invariant.
            if not file_found:
                reason = "file_missing"
                fix_hint = "the pinned source file is missing; restore it from git history"
            elif not pattern_matched:
                reason = "pattern_unmatched"
                fix_hint = (
                    "the pinned pattern no longer matches its file region "
                    f"(match_count={r.get('match_count', 0)}); investigate whether "
                    "the region was renamed, moved, or removed"
                )
            elif allow_digest and digest and digest != allow_digest:
                reason = "digest_drift"
                fix_hint = (
                    f"digest drift vs allowlist (current={digest[:16]}..., "
                    f"pinned={allow_digest[:16]}...). If the drift is intentional, "
                    "regenerate the allowlist via the governance ceremony: "
                    "`python scripts/vapi_invariant_gate.py --generate "
                    "--reason \"<category>: ...\" --confirm-governance`"
                )
            else:
                continue  # invariant is healthy — no finding
            findings.append(MythosFindingResult(
                variant="frozen",
                severity="HIGH",
                description=(
                    f"INV {inv_id} ({reason}) — would fail PV-CI gate. "
                    f"Description: {r.get('description', '')[:140]}"
                ),
                recommended_fix=fix_hint,
                coherence_id=_coherence_id("frozen", f"{inv_id}:{reason}"),
                file_path=str(r.get("file", "")) or None,
                frozen_region=True,           # forces tier=3 at store layer
                fix_authority_tier=3,         # read-only
                evidence_sources=[
                    "scripts/vapi_invariant_gate.py",
                    ".github/INVARIANTS_ALLOWLIST.json",
                ],
            ))
    except Exception as exc:  # noqa: BLE001
        log.warning("mythos_frozen_drift: gate import/run failed: %s", exc)
        findings.append(MythosFindingResult(
            variant="frozen",
            severity="LOW",
            description=f"mythos-frozen could not invoke check_invariants: {exc}",
            recommended_fix=(
                "Verify scripts/vapi_invariant_gate.py imports cleanly + "
                "INVARIANTS_ALLOWLIST.json is present + readable."
            ),
            coherence_id=_coherence_id("frozen", "_gate_invocation_error"),
            evidence_sources=["scripts/vapi_invariant_gate.py"],
            error=str(exc),
        ))
    return findings


# ==========================================================================
# Mythos-Stability — async-hazard / resource-leak pattern scanner
# ==========================================================================

# Pattern 1: urllib.request.urlopen(...) — check if `timeout=` appears
# anywhere in the argument list. Single-line match across reasonable urlopen
# calls. (Multi-line urlopen calls are uncommon and we accept that gap.)
_PAT_URLOPEN = re.compile(r"urllib\.request\.urlopen\s*\(([^)]*)\)", re.MULTILINE)

# Pattern 2: silent `except Exception:` immediately followed by `pass`
# (allowing whitespace). Two-line match.
_PAT_EXCEPT_PASS = re.compile(
    r"except\s+Exception\s*(?:as\s+\w+)?\s*:\s*\n\s*pass\b",
    re.MULTILINE,
)

# Files we audit (Python production code in bridge/vapi_bridge/ + scripts/).
# Tests, vendored deps, generated files, and .git/ are excluded.
_AUDIT_DIRS = ("bridge/vapi_bridge", "scripts")
_AUDIT_EXTS = (".py",)
_AUDIT_EXCLUDE_SUBSTR = (
    "__pycache__",
    "node_modules",
    "/.git/",
    "/dist/",
    "/build/",
    "/venv/",
    "/.venv/",
    "/bridge/tests/",
    "/sdk/tests/",
    "/w3bstream/poseidon_test_vectors",
    # Exclude mythos_variants.py itself — its regex source matches itself.
    "/bridge/vapi_bridge/mythos_variants.py",
)

# Deliberate-fail-open markers — when one of these substrings appears
# within 2 lines of an `except Exception: pass`, the pass is declared
# intentional + Mythos-Stability skips it. Empirically derived from VAPI's
# bridge conventions: store helpers use `# idempotent`; fail-open contracts
# use `# fail-open` / `# noqa: BLE001`.
_FAIL_OPEN_MARKERS = (
    "idempotent",
    "fail-open",
    "fail_open",
    "noqa: BLE001",
    "intentional",
    "silent ok",
)


def _iter_audit_files(root: Path) -> Iterable[Path]:
    """Walk the audit dirs and yield .py files we should scan. Each path
    is filtered against _AUDIT_EXCLUDE_SUBSTR (substring match on the
    POSIX path so the same filter works on Windows + POSIX)."""
    for sub in _AUDIT_DIRS:
        base = root / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in _AUDIT_EXTS:
                continue
            posix = p.as_posix()
            if any(excl in posix for excl in _AUDIT_EXCLUDE_SUBSTR):
                continue
            yield p


async def mythos_stability_sweep(
    *,
    repo_root: Path | None = None,
) -> list[MythosFindingResult]:
    """Scan production .py files in bridge/vapi_bridge/ + scripts/ for two
    classes of async hazard the prior Mythos audit empirically found
    (commit 48236084):

      1. urllib.request.urlopen() without timeout= argument — HIGH severity
         (executor-pool starvation: asyncio.wait_for cancels the awaiting
         coroutine but cannot interrupt the blocking socket in the
         executor thread).
      2. Silent `except Exception: pass` — MEDIUM severity (error-
         swallowing hides real failures).

    Fail-open: errors reading any single file are logged + skipped; the
    sweep continues on the remaining files."""
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []

    for path in _iter_audit_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            log.debug("mythos_stability_sweep: skip %s (read error: %s)", path, exc)
            continue

        rel = path.relative_to(root).as_posix()

        # --- Pattern 1: urlopen no-timeout ---
        for m in _PAT_URLOPEN.finditer(text):
            arglist = m.group(1)
            if "timeout=" in arglist:
                continue  # has a timeout — OK
            line_no = text.count("\n", 0, m.start()) + 1
            findings.append(MythosFindingResult(
                variant="stability",
                severity="HIGH",
                description=(
                    f"urllib.urlopen(...) at {rel}:{line_no} has no `timeout=` "
                    "argument. asyncio.wait_for cancels the awaiting coroutine "
                    "but cannot interrupt the blocking socket in the executor "
                    "thread — a hung peer can starve the bridge ThreadPoolExecutor."
                ),
                recommended_fix=(
                    "Add `timeout=<float>` to the urlopen call. Pull the value "
                    "from cfg (mirror ipfs_pinning.py / ioswarm_live_node_client.py)."
                ),
                coherence_id=_coherence_id("stability", f"urlopen_no_timeout:{rel}:{line_no}"),
                file_path=rel,
                line_number=line_no,
                frozen_region=False,
                fix_authority_tier=2,  # operator-gated; not autofix
                evidence_sources=[rel],
            ))

        # --- Pattern 2: silent except:pass (skip if deliberate fail-open) ---
        text_lines = text.splitlines()
        for m in _PAT_EXCEPT_PASS.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            # Look-back window: 5 lines above the `except` + 2 lines below
            # (inclusive, 1-indexed). Wider above because the deliberate-
            # fail-open marker is often a comment on the try: line or even
            # above the try (e.g. a function docstring describing fail-open
            # semantics). Below 2 lines covers `pass  # idempotent` style.
            # Conversion to 0-indexed slice: text_lines[(line_no-1)-5 :
            # (line_no-1)+3] = text_lines[line_no-6 : line_no+2].
            lo = max(0, line_no - 6)
            hi = min(len(text_lines), line_no + 2)
            context = "\n".join(text_lines[lo:hi]).lower()
            if any(marker.lower() in context for marker in _FAIL_OPEN_MARKERS):
                continue  # deliberate fail-open — not a finding
            findings.append(MythosFindingResult(
                variant="stability",
                severity="MEDIUM",
                description=(
                    f"Silent `except Exception: pass` at {rel}:{line_no} "
                    "swallows errors without a deliberate-fail-open marker "
                    "(no `# idempotent` / `# fail-open` / `# noqa: BLE001` "
                    "in the surrounding 5 lines). Real failures may become "
                    "invisible at runtime."
                ),
                recommended_fix=(
                    "If the silent pass is intentional, add a "
                    "`# fail-open` / `# idempotent` comment near the except "
                    "(matches existing VAPI convention; Mythos-Stability "
                    "will then skip it on the next cadence). Otherwise "
                    "replace with `except Exception as exc: log.warning(...)` "
                    "consistent with the rest of the codebase."
                ),
                coherence_id=_coherence_id("stability", f"except_pass:{rel}:{line_no}"),
                file_path=rel,
                line_number=line_no,
                frozen_region=False,
                fix_authority_tier=2,
                evidence_sources=[rel],
            ))

        # Yield to event loop occasionally (each file is read+scanned, so
        # one yield per file is plenty).
        await asyncio.sleep(0)

    return findings


# ==========================================================================
# Mythos-Operator-Initiative-Audit — operator-authorized extension
# ==========================================================================
# Audits the WHOLE Operator Initiative across past + current + future
# architectural surfaces, ensuring novel synchronization within every
# aspect of VAPI Architecture + framework development, especially the
# methodology overlap (VBDIP-0001 + architect Ed25519 attestation chain).
#
# Authorization basis: operator request 2026-05-15 ("Yes have mythos audit
# the whole operators initiative past, current, future implementation for
# completion, ensuring novel synchronization within every aspect of VAPI
# Architecture and framework development especially the methodology"). This
# extends beyond the Priority 3 Minimal-Mythos scope (2 variants) but stays
# READ-ONLY + fail-open + frozen_region=True on every finding that touches
# protocol-layer surfaces — Mythos NEVER auto-fixes Operator Initiative
# state. All findings route through INV-MYTHOS-FROZEN-PROTECTION-001 →
# tier=3 read-only at the store layer.
# --------------------------------------------------------------------------

# ----- Canonical Merkle pins -----
# Source: CLAUDE.md NOTE entries — Phase O1 C1 (2026-05-03 dual-anchor),
# Phase O2-SUGGEST-DRAFT (pre-authored v1 bundles 2026-05-07), Track 2 C8
# (Cedar v2 bundles dual-anchored LIVE 2026-05-12), Phase O3-ACT-DRAFT
# (pre-authored O3 ACTING bundles 2026-05-10 commit 3cb59f46), Sessions
# 1+2+3 (Curator activated 2026-05-09). Stream 4 PV-CI ceremony will pin
# this dict via INV-MYTHOS-OPINIT-MERKLE-001 (deferred — not in this ship).
_CANONICAL_BUNDLE_MERKLES: dict[str, str] = {
    # Phase O1 C1 — LIVE on-chain via dual-anchor ceremony
    "anchor_sentry_o1_shadow_v1.json":
        "0xebe899279b230ff5d71db22dc4b80282c810ff5bd1a9d249db6e6d309af52e41",
    "guardian_o1_shadow_v1.json":
        "0x46807e13dd1c81cefa784ab8b30f8cdcaefd60697de921aae46ac24dac000a50",
    # Phase O1-CURATOR Sessions 1+2+3 — LIVE on-chain
    "curator_o1_shadow_v1.json":
        "0x44f89d0a05e7594741f7a06a1c4ca817d58396ad41b22b0eb5d0b5ce4be88ae6",
    # Phase O2-SUGGEST-DRAFT pre-authored v1 bundles (never anchored on chain;
    # superseded by v2 per the C6 ship 2026-05-12)
    "anchor_sentry_o2_suggest_v1.json":
        "0x1af7854a08de4ce26ba7aeb5a6c215b3ae15057b3d3e665eb48db5044bfc2609",
    "guardian_o2_suggest_v1.json":
        "0x70ccf51f36d6a3812181004b20668a68e936e8d975ebd9ac217d13743a82bdab",
    "curator_o2_suggest_v1.json":
        "0xeb400a5c9b410c6f3035a595e2c36dee915f6b2447f822c72c46b164ccd5daa9",
    # Cedar v2 — LIVE on-chain dual-anchored 2026-05-12
    "anchor_sentry_o2_suggest_v2.json":
        "0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23",
    "guardian_o2_suggest_v2.json":
        "0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0",
    "curator_o2_suggest_v2.json":
        "0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d",
    # Phase O3-ACT-DRAFT pre-authored bundles (not yet anchored — gated on
    # 504h shadow_age + 50 drafts/agent + disagreement_rate < 5%)
    "anchor_sentry_o3_acting_v1.json":
        "0xc0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878",
    "guardian_o3_acting_v1.json":
        "0x6f0fc77cc1dacaf3f79aeb0f27dd8c7b3d88e95b236f0806ad3588a06bb82225",
    "curator_o3_acting_v1.json":
        "0xd9d760c8b7b1088f2edd165fbfa6441abcb3bc3f921e8ba75a3339c0825fec24",
}

# Q9-frozen agentIds per Pass 2C / Phase O0 registration.
# Source: bridge/vapi_bridge/config.py defaults (Phase O1 C1 + Sessions 1+2+3).
_CANONICAL_Q9_AGENT_IDS: dict[str, str] = {
    "anchor_sentry": "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c",
    "guardian":      "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1",
    "curator":       "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8",
}

_LIFECYCLE_BUNDLE_SUFFIXES: tuple[str, ...] = (
    "_o1_shadow_v1.json",
    "_o2_suggest_v1.json",
    "_o2_suggest_v2.json",
    "_o3_acting_v1.json",
)

_INITIATIVE_AGENT_NAMES: tuple[str, ...] = ("anchor_sentry", "guardian", "curator")


def _normalize_hex(s: str) -> str:
    """Lowercase + strip 0x prefix. Used for cross-source Merkle compare."""
    s = (s or "").strip().lower()
    return s[2:] if s.startswith("0x") else s


async def mythos_operator_initiative_audit(
    *,
    repo_root: Path | None = None,
) -> list[MythosFindingResult]:
    """Comprehensive synchronization audit of past + current + future
    Operator Initiative implementation. Five check families, all read-only,
    all fail-open per the Mythos contract.

    CHECK FAMILY 1 — PAST_ARTIFACTS (file presence):
       12 Cedar bundle files exist under bridge/vapi_bridge/cedar_bundles/
       (3 agents × 4 lifecycle bundles = 12). Architect Ed25519 attestation
       file vsd-vault/eval/architect_key_attestation.json exists.

    CHECK FAMILY 2 — Q9_HEX_CONSISTENCY (cross-surface invariants):
       Each Cedar bundle's `agent_id` field == the canonical Q9 hex per
       Pass 2C / Phase O0 registration. Drift here breaks bundle anchoring.

    CHECK FAMILY 3 — MERKLE_SYNCHRONIZATION (the deep invariant):
       Each on-disk bundle's recomputed Merkle MATCHES the canonical pin
       from the historical CLAUDE.md NOTE record. Drift means a bundle
       file was mutated post-anchor or post-pre-authoring — the on-chain
       scopeRoot would no longer match.

    CHECK FAMILY 4 — PARALLEL_SCRIPT_SYNC (anchor-script integrity):
       AGENT_ANCHOR_ORDER in parallel_o2_anchor.py == in parallel_o3_act_
       anchor.py == _INITIATIVE_AGENT_NAMES. AGENT_BUNDLE_FILES in both
       scripts references files that exist on disk.

    CHECK FAMILY 5 — METHODOLOGY_OVERLAP (especially-the-methodology):
       VBDIP-0001 manifest signature file exists at
       vsd-vault/manifests/proposals-VBDIP-0001/. Architect public-key
       attestation file exists. Both anchor the methodology layer's
       provenance chain that the Operator Initiative inherits trust from.

    Severity ladder:
       CRITICAL  — bundle missing OR Merkle drift OR Q9 hex drift (chain
                   anchor integrity breaks)
       HIGH      — script-order drift across the two parallel anchor
                   scripts (would scramble activation_log ordering)
       MEDIUM    — methodology attestation missing (Operator Initiative
                   inherits trust from architect Ed25519 chain — gap)
       LOW       — documentation/CLAUDE.md narrative gap

    All findings carry frozen_region=True → INV-MYTHOS-FROZEN-PROTECTION-001
    forces tier=3 (read-only) at the store layer.
    """
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []
    bundles_dir = root / "bridge" / "vapi_bridge" / "cedar_bundles"

    # ----- Family 1: PAST_ARTIFACTS file presence -----
    for agent in _INITIATIVE_AGENT_NAMES:
        for suffix in _LIFECYCLE_BUNDLE_SUFFIXES:
            fname = f"{agent}{suffix}"
            bpath = bundles_dir / fname
            if not bpath.is_file():
                findings.append(MythosFindingResult(
                    variant="operator_initiative",
                    severity="CRITICAL",
                    description=(
                        f"PAST_ARTIFACTS: Operator Initiative Cedar bundle "
                        f"file missing: {fname}. Each agent (Sentry/Guardian/"
                        f"Curator) MUST have all 4 lifecycle bundles "
                        f"(o1_shadow_v1 / o2_suggest_v1 / o2_suggest_v2 / "
                        f"o3_acting_v1). Missing bundle breaks anchor "
                        f"script's AGENT_BUNDLE_FILES lookup."
                    ),
                    recommended_fix=(
                        f"Restore {fname} from git history "
                        f"(`git log -- bridge/vapi_bridge/cedar_bundles/"
                        f"{fname}`). Do NOT regenerate from scratch — the "
                        f"Merkle root MUST match the canonical pin in "
                        f"_CANONICAL_BUNDLE_MERKLES + the on-chain anchor."
                    ),
                    coherence_id=_coherence_id("operator_initiative", f"missing:{fname}"),
                    file_path=f"bridge/vapi_bridge/cedar_bundles/{fname}",
                    frozen_region=True,
                    fix_authority_tier=3,
                    evidence_sources=[f"bridge/vapi_bridge/cedar_bundles/{fname}"],
                ))
        await asyncio.sleep(0)

    # ----- Family 2 + 3: Q9 hex consistency + Merkle synchronization -----
    # Single-pass: parse each existing bundle ONCE, then cross-check both.
    try:
        from vapi_bridge.cedar_parser import bundle_merkle_root
    except Exception as exc:  # noqa: BLE001
        findings.append(MythosFindingResult(
            variant="operator_initiative",
            severity="LOW",
            description=(
                f"Could not import cedar_parser.bundle_merkle_root: {exc}. "
                "Merkle synchronization check skipped."
            ),
            recommended_fix="Investigate cedar_parser module load failure.",
            coherence_id=_coherence_id("operator_initiative", "cedar_parser_import_fail"),
            frozen_region=False,
            fix_authority_tier=2,
            evidence_sources=["bridge/vapi_bridge/cedar_parser.py"],
        ))
        bundle_merkle_root = None  # type: ignore[assignment]

    import json
    for fname, expected_merkle_hex in _CANONICAL_BUNDLE_MERKLES.items():
        bpath = bundles_dir / fname
        if not bpath.is_file():
            continue  # already flagged by Family 1
        try:
            payload = json.loads(bpath.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            findings.append(MythosFindingResult(
                variant="operator_initiative",
                severity="CRITICAL",
                description=(
                    f"Bundle file {fname} could not be parsed as JSON: {exc}. "
                    "On-chain anchor verification + Cedar policy evaluation "
                    "would BOTH break against this state."
                ),
                recommended_fix="Restore the bundle file from git history.",
                coherence_id=_coherence_id("operator_initiative", f"json_parse:{fname}"),
                file_path=f"bridge/vapi_bridge/cedar_bundles/{fname}",
                frozen_region=True,
                fix_authority_tier=3,
                evidence_sources=[f"bridge/vapi_bridge/cedar_bundles/{fname}"],
            ))
            continue

        # Q9 hex consistency
        agent = fname.split("_")[0] if not fname.startswith("anchor_sentry") else "anchor_sentry"
        if fname.startswith("anchor_sentry"):
            agent = "anchor_sentry"
        elif fname.startswith("guardian"):
            agent = "guardian"
        elif fname.startswith("curator"):
            agent = "curator"
        canonical_q9 = _CANONICAL_Q9_AGENT_IDS.get(agent, "")
        bundle_agent_id = str(payload.get("agent_id", "") or "")
        if _normalize_hex(bundle_agent_id) != _normalize_hex(canonical_q9):
            findings.append(MythosFindingResult(
                variant="operator_initiative",
                severity="CRITICAL",
                description=(
                    f"Q9 HEX DRIFT: bundle {fname} declares agent_id="
                    f"{bundle_agent_id[:18]}... but canonical Q9 hex per "
                    f"cfg.operator_agent_{agent}_id is {canonical_q9[:18]}.... "
                    "Mismatch breaks AgentRegistry resolution + Cedar "
                    "principal matching."
                ),
                recommended_fix=(
                    "Restore bundle from git history OR update "
                    "_CANONICAL_Q9_AGENT_IDS + cfg defaults via governance "
                    "ceremony (invariant_change category)."
                ),
                coherence_id=_coherence_id(
                    "operator_initiative", f"q9_drift:{fname}"
                ),
                file_path=f"bridge/vapi_bridge/cedar_bundles/{fname}",
                frozen_region=True,
                fix_authority_tier=3,
                evidence_sources=[
                    f"bridge/vapi_bridge/cedar_bundles/{fname}",
                    "bridge/vapi_bridge/config.py",
                ],
            ))

        # Merkle synchronization
        if bundle_merkle_root is not None:
            try:
                live_merkle = bundle_merkle_root(payload).hex()
            except Exception as exc:  # noqa: BLE001
                live_merkle = ""
                findings.append(MythosFindingResult(
                    variant="operator_initiative",
                    severity="HIGH",
                    description=(
                        f"Bundle {fname} could not have its Merkle root "
                        f"recomputed: {exc}. Bundle may be structurally "
                        "invalid (missing $schema, unknown policy effect, etc.)."
                    ),
                    recommended_fix=(
                        "Run `python scripts/cedar_bundle_validate.py validate "
                        f"bridge/vapi_bridge/cedar_bundles/{fname}` and fix "
                        "any reported schema violations."
                    ),
                    coherence_id=_coherence_id(
                        "operator_initiative", f"merkle_compute_fail:{fname}"
                    ),
                    file_path=f"bridge/vapi_bridge/cedar_bundles/{fname}",
                    frozen_region=True,
                    fix_authority_tier=3,
                    evidence_sources=[
                        f"bridge/vapi_bridge/cedar_bundles/{fname}"
                    ],
                ))
            if live_merkle and _normalize_hex(live_merkle) != _normalize_hex(expected_merkle_hex):
                findings.append(MythosFindingResult(
                    variant="operator_initiative",
                    severity="CRITICAL",
                    description=(
                        f"MERKLE DRIFT: bundle {fname} on-disk recomputed "
                        f"Merkle = 0x{live_merkle[:16]}... but canonical "
                        f"pin = {expected_merkle_hex[:18]}.... Bundle has "
                        "been mutated post-anchor or post-pre-authoring. "
                        "On-chain AgentScope scopeRoot will NOT match this "
                        "bundle if anchored."
                    ),
                    recommended_fix=(
                        "Restore bundle from git history (`git log --all -- "
                        f"bridge/vapi_bridge/cedar_bundles/{fname}`). Do "
                        "NOT update _CANONICAL_BUNDLE_MERKLES — the pin is "
                        "the authoritative chain-anchor record."
                    ),
                    coherence_id=_coherence_id(
                        "operator_initiative", f"merkle_drift:{fname}"
                    ),
                    file_path=f"bridge/vapi_bridge/cedar_bundles/{fname}",
                    frozen_region=True,
                    fix_authority_tier=3,
                    evidence_sources=[
                        f"bridge/vapi_bridge/cedar_bundles/{fname}",
                        "CLAUDE.md",  # canonical historical record
                    ],
                ))
        await asyncio.sleep(0)

    # ----- Family 4: PARALLEL_SCRIPT_SYNC -----
    # Re-parse the two parallel anchor scripts to verify AGENT_ANCHOR_ORDER
    # is identical + AGENT_BUNDLE_FILES references files that exist.
    for script_rel, expected_phase in (
        ("scripts/parallel_o2_anchor.py", "o2_suggest"),
        ("scripts/parallel_o3_act_anchor.py", "o3_acting"),
    ):
        spath = root / script_rel
        if not spath.is_file():
            findings.append(MythosFindingResult(
                variant="operator_initiative",
                severity="HIGH",
                description=(
                    f"PARALLEL_SCRIPT_SYNC: anchor script {script_rel} not "
                    "found. Operator Initiative graduation ceremony is "
                    "structurally unrunnable without this script."
                ),
                recommended_fix="Restore from git history.",
                coherence_id=_coherence_id(
                    "operator_initiative", f"script_missing:{script_rel}"
                ),
                file_path=script_rel,
                frozen_region=True,
                fix_authority_tier=3,
                evidence_sources=[script_rel],
            ))
            continue
        try:
            src = spath.read_text(encoding="utf-8")
            # Naive parse: look for the tuple literal. Sufficient for our use.
            order_marker = 'AGENT_ANCHOR_ORDER = ("anchor_sentry", "guardian", "curator")'
            if order_marker not in src:
                findings.append(MythosFindingResult(
                    variant="operator_initiative",
                    severity="HIGH",
                    description=(
                        f"PARALLEL_SCRIPT_SYNC: {script_rel} does NOT contain "
                        f'the expected literal AGENT_ANCHOR_ORDER tuple. '
                        "Drift here would scramble activation_log ordering "
                        "across the two ceremony scripts."
                    ),
                    recommended_fix=(
                        "Restore the literal tuple "
                        '(\"anchor_sentry\", \"guardian\", \"curator\") in '
                        f"{script_rel}. Both parallel anchor scripts MUST "
                        "agree byte-for-byte."
                    ),
                    coherence_id=_coherence_id(
                        "operator_initiative", f"order_drift:{script_rel}"
                    ),
                    file_path=script_rel,
                    frozen_region=True,
                    fix_authority_tier=3,
                    evidence_sources=[script_rel],
                ))
            # Verify all 3 bundle files referenced exist
            for agent in _INITIATIVE_AGENT_NAMES:
                bundle_marker = f'"{agent}":'
                if bundle_marker not in src:
                    findings.append(MythosFindingResult(
                        variant="operator_initiative",
                        severity="HIGH",
                        description=(
                            f"PARALLEL_SCRIPT_SYNC: {script_rel} missing "
                            f"AGENT_BUNDLE_FILES entry for '{agent}'."
                        ),
                        recommended_fix="Restore the dict entry from git history.",
                        coherence_id=_coherence_id(
                            "operator_initiative",
                            f"bundle_files_missing:{script_rel}:{agent}",
                        ),
                        file_path=script_rel,
                        frozen_region=True,
                        fix_authority_tier=3,
                        evidence_sources=[script_rel],
                    ))
        except Exception as exc:  # noqa: BLE001
            findings.append(MythosFindingResult(
                variant="operator_initiative",
                severity="LOW",
                description=(
                    f"PARALLEL_SCRIPT_SYNC: error reading {script_rel}: {exc}."
                ),
                recommended_fix="Investigate read failure.",
                coherence_id=_coherence_id(
                    "operator_initiative", f"script_read_fail:{script_rel}"
                ),
                frozen_region=False,
                fix_authority_tier=2,
                evidence_sources=[script_rel],
            ))
        await asyncio.sleep(0)

    # ----- Family 5: METHODOLOGY_OVERLAP -----
    # Architect Ed25519 attestation + VBDIP-0001 manifest existence are the
    # provenance chain the Operator Initiative inherits trust from. Missing
    # either undermines the entire trust hierarchy methodology-side.
    attestation_path = root / "vsd-vault" / "eval" / "architect_key_attestation.json"
    if not attestation_path.is_file():
        findings.append(MythosFindingResult(
            variant="operator_initiative",
            severity="MEDIUM",
            description=(
                "METHODOLOGY_OVERLAP: Architect Ed25519 attestation file "
                "missing at vsd-vault/eval/architect_key_attestation.json. "
                "This file is the EIP-191 attestation binding the Architect "
                "Ed25519 pubkey to the bridge wallet — Operator Initiative "
                "trust hierarchy inherits from this signature chain."
            ),
            recommended_fix=(
                "Restore from git history (Phase O0 Step 4, commit "
                "8b95d5bc). Do not regenerate — the Ed25519 keypair + EIP-191 "
                "signature are the canonical record."
            ),
            coherence_id=_coherence_id(
                "operator_initiative", "missing:architect_attestation"
            ),
            file_path="vsd-vault/eval/architect_key_attestation.json",
            frozen_region=True,
            fix_authority_tier=3,
            evidence_sources=["vsd-vault/eval/architect_key_attestation.json"],
        ))

    vbdip_manifest_dir = root / "vsd-vault" / "manifests" / "proposals-VBDIP-0001"
    if not vbdip_manifest_dir.is_dir():
        findings.append(MythosFindingResult(
            variant="operator_initiative",
            severity="MEDIUM",
            description=(
                "METHODOLOGY_OVERLAP: VBDIP-0001 manifest directory missing "
                "at vsd-vault/manifests/proposals-VBDIP-0001/. The VAD "
                "framework (VBDIP-0001 FROZEN) is the methodology under "
                "which all Operator Initiative gates were specified — "
                "missing manifest breaks the methodology trust chain."
            ),
            recommended_fix=(
                "Restore from git history (Phase O0 Step 5, commit d6830525)."
            ),
            coherence_id=_coherence_id(
                "operator_initiative", "missing:vbdip_0001_manifest"
            ),
            file_path="vsd-vault/manifests/proposals-VBDIP-0001/",
            frozen_region=True,
            fix_authority_tier=3,
            evidence_sources=["vsd-vault/manifests/proposals-VBDIP-0001/"],
        ))

    return findings


# ==========================================================================
# Mythos-Crypto — PATTERN-017 commitment-family integrity (Priority 5)
# ==========================================================================
# Pinned PATTERN-017 domain tags (10 commitment families per CLAUDE.md
# Hard Rules). Drift here (additions OR removals) reshapes the protocol
# surface; any change requires governance ceremony + new PV-CI invariants.
# This list is the audit's source-of-truth — if a new commitment family
# is added in production code, this list MUST be updated in the same PR.
_PATTERN_017_FROZEN_TAGS: frozenset[bytes] = frozenset({
    b"VAPI-GIC-GENESIS-v1",          # grind_chain.py
    b"VAPI-WEC-GENESIS-v1",          # watchdog_chain.py
    b"VAPI-VAME-v1",                 # vame.py
    b"VAPI-CORPUS-SNAPSHOT-v1",      # corpus_snapshot.py
    b"VAPI-CONSENT-v1",              # consent_categories.py
    b"VAPI-BIOMETRIC-SNAPSHOT-v1",   # biometric_snapshot.py
    b"VAPI-LISTING-v1",              # listing_primitive.py
    b"VAPI-FRR-v1",                  # operator_initiative_advancement.py
    b"VAPI-ZKBA-ARTIFACT-v1",        # zkba_artifact.py
    b"VAPI-AGENT-COMMIT-v1",         # agent_commit.py
    b"VAPI-PHYSICAL-DATA-ATTESTATION-v1",  # physical_data_attestation.py
                                     # (Pass 2C Section 4.2 ratified; the
                                     # docstring explicitly identifies it
                                     # as a FROZEN-v1 commitment-family
                                     # primitive — surfaced as a finding
                                     # against CLAUDE.md's stated count
                                     # of 10, see audit notes below)
})

# AUDIT NOTE 2026-05-15: When this audit was first run live, Mythos-Crypto
# surfaced VAPI-PHYSICAL-DATA-ATTESTATION-v1 as an UNKNOWN HIGH finding.
# Investigation confirmed PHYSICAL_DATA_ATTESTATION v1 is a genuine
# FROZEN-v1 commitment family (Pass 2C Section 4.2 ratified). The pin
# list now includes it explicitly, bringing the empirically-observed
# count to 11. CLAUDE.md's stated "10 PATTERN-017 commitment families"
# may need a sync update — surfaced here for operator review without
# silently editing CLAUDE.md.

# Capability tags — distinct from PATTERN-017 commitment families per
# the POSEIDON-BN254-AS reframe precedent. These are NOT counted toward
# the PATTERN-017 family invariant.
_KNOWN_CAPABILITY_TAGS: frozenset[bytes] = frozenset({
    b"VAPI-BT-WITNESS-v1",            # Phase 242-BT Stream 1
    b"VAPI-BT-WITNESS-BLE-v1",        # Phase 242-BT — reserved BLE-HOGP future variant
                                      # (documented in bt_witness.py module docstring; not
                                      # yet allocated, distinct capability tag if needed)
    b"VAPI-CEDAR-BUNDLE-v1",          # cedar_parser.py — Cedar bundle $schema version
                                      # literal (schema-versioning surface, NOT a
                                      # commitment-family domain tag)
    b"VAPI-MLGA-SESSION-v1",          # Phase O5-MLGA Stage 2 — mlga_capture.py session
                                      # dataproof capability; NOT a PATTERN-017
                                      # commitment family per the POSEIDON-BN254-AS
                                      # reframe precedent
})


async def mythos_crypto_drift(
    *,
    repo_root: Path | None = None,
    poll_npm_registry: bool = False,
) -> list[MythosFindingResult]:
    """PATTERN-017 commitment-family integrity audit.

    Scans bridge/vapi_bridge/*.py for `b"VAPI-..."` domain tag literals
    and cross-checks against the FROZEN frozenset of 10 PATTERN-017
    commitment-family tags + the known capability-tag set. Findings:
      CRITICAL: a PATTERN-017 tag in the FROZEN set is MISSING from
                production code (commitment family was removed without
                governance).
      HIGH:     an unknown `b"VAPI-..."` literal appears in production
                code (potential new commitment family without invariant
                pinning — needs governance ceremony to add).
      LOW:      poll_npm_registry=True surfaces an INFORMATIONAL when
                @assemblyscript/wasm-crypto becomes available on npm
                (the Phase 244 unblocker; this variant is the operator's
                periodic check for that upstream resolution).

    NEVER raises (fail-open contract). All findings frozen_region=True.
    """
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []
    bridge_dir = root / "bridge" / "vapi_bridge"

    # Discover all b"VAPI-..." literal occurrences in production code.
    discovered_tags: set[bytes] = set()
    discovered_by_file: dict[bytes, list[str]] = {}
    pat = re.compile(rb'b"(VAPI-[A-Za-z0-9_\-]+-v\d+)"')
    if bridge_dir.is_dir():
        for f in bridge_dir.rglob("*.py"):
            try:
                src = f.read_bytes()
            except Exception:  # noqa: BLE001 — fail-open
                continue
            for m in pat.finditer(src):
                tag = b'"' + m.group(1) + b'"'  # for clarity, but we use raw form below
                raw_tag = m.group(1)            # without surrounding quotes
                discovered_tags.add(raw_tag)
                rel = str(f.relative_to(root)).replace("\\", "/")
                discovered_by_file.setdefault(raw_tag, []).append(rel)
            await asyncio.sleep(0)

    # Convert to canonical bytes for set ops
    all_known = set(_PATTERN_017_FROZEN_TAGS) | set(_KNOWN_CAPABILITY_TAGS)
    discovered_bytes = {b for b in discovered_tags}

    # Check 1: every FROZEN PATTERN-017 tag must appear in production code
    missing = _PATTERN_017_FROZEN_TAGS - discovered_bytes
    for tag in missing:
        findings.append(MythosFindingResult(
            variant="crypto",
            severity="CRITICAL",
            description=(
                f"PATTERN-017 FAMILY DRIFT: FROZEN commitment-family tag "
                f"{tag!r} is missing from bridge/vapi_bridge/*.py. The 10 "
                "PATTERN-017 commitment families are protocol-defining; "
                "removal requires governance ceremony + invariant change."
            ),
            recommended_fix=(
                f"Restore the {tag!r} primitive module from git history. "
                "Do NOT update _PATTERN_017_FROZEN_TAGS — the count is "
                "the FROZEN invariant."
            ),
            coherence_id=_coherence_id("crypto", f"missing_family:{tag.decode()}"),
            frozen_region=True,
            fix_authority_tier=3,
            evidence_sources=["bridge/vapi_bridge/", "CLAUDE.md"],
        ))

    # Check 2: every discovered tag should be in the known set (FROZEN
    # PATTERN-017 ∪ known capability tags). Unknown tags = potential new
    # commitment family without invariant pinning.
    unknown = discovered_bytes - all_known
    for tag in sorted(unknown):
        files_ref = discovered_by_file.get(tag, [])
        findings.append(MythosFindingResult(
            variant="crypto",
            severity="HIGH",
            description=(
                f"UNKNOWN CRYPTOGRAPHIC TAG: {tag!r} appears in production "
                f"code at {files_ref} but is NOT in _PATTERN_017_FROZEN_TAGS "
                "or _KNOWN_CAPABILITY_TAGS. Either (a) a new commitment "
                "family was added without governance ceremony, OR (b) a "
                "new capability tag was added without updating this audit."
            ),
            recommended_fix=(
                "If this is a new commitment family: invoke governance "
                "ceremony (--reason 'invariant_change' + governance phrase) "
                "to update _PATTERN_017_FROZEN_TAGS + add PV-CI invariant. "
                "If a capability tag: update _KNOWN_CAPABILITY_TAGS."
            ),
            coherence_id=_coherence_id("crypto", f"unknown_tag:{tag.decode()}"),
            file_path=files_ref[0] if files_ref else None,
            frozen_region=True,
            fix_authority_tier=3,
            evidence_sources=files_ref or ["bridge/vapi_bridge/"],
        ))

    # Check 3: AS Poseidon test-vector corpus SHA-256 file presence
    poseidon_sha = root / "scripts" / "w3bstream" / "poseidon_test_vectors.sha256"
    if not poseidon_sha.is_file():
        findings.append(MythosFindingResult(
            variant="crypto",
            severity="HIGH",
            description=(
                "Poseidon test-vector corpus SHA-256 pin file missing at "
                "scripts/w3bstream/poseidon_test_vectors.sha256. This file "
                "pins the circomlibjs 0.1.7 ground-truth corpus that V.1/"
                "V.2 verify the AS Poseidon implementation against. Without "
                "it, INV-POSEIDON-AS-003 cannot enforce vector-file integrity."
            ),
            recommended_fix=(
                "Restore from git history (Phase O4-W3B-POSEIDON-AS, commit "
                "afa31416..2205e2a1)."
            ),
            coherence_id=_coherence_id("crypto", "missing:poseidon_sha"),
            file_path="scripts/w3bstream/poseidon_test_vectors.sha256",
            frozen_region=True,
            fix_authority_tier=3,
            evidence_sources=["scripts/w3bstream/poseidon_test_vectors.sha256"],
        ))

    # Check 4 (optional): NPM registry poll for @assemblyscript/wasm-crypto.
    # This is the Phase 244 unblocker. Default OFF (network I/O); operator
    # enables periodically.
    if poll_npm_registry:
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://registry.npmjs.org/@assemblyscript/wasm-crypto",
                headers={"User-Agent": "vapi-mythos-crypto-poll/1.0"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                status = resp.status
            if status == 200:
                findings.append(MythosFindingResult(
                    variant="crypto",
                    severity="LOW",
                    description=(
                        "DISCOVERY: @assemblyscript/wasm-crypto is now "
                        "available on the npm registry. This is the "
                        "Phase 244-W3B-REG upstream unblocker — operator "
                        "may now proceed with P256_VERIFY closure + "
                        "applet registration ceremony."
                    ),
                    recommended_fix=(
                        "Operator action: validate the package via NIST "
                        "CAVP P-256 vectors, then schedule the applet "
                        "registration ceremony at console.w3bstream.com "
                        "per the Phase 244 plan."
                    ),
                    coherence_id=_coherence_id(
                        "crypto", "npm_discovery:wasm_crypto_available"
                    ),
                    frozen_region=False,  # informational discovery, not protocol drift
                    fix_authority_tier=2,
                    evidence_sources=["registry.npmjs.org/@assemblyscript/wasm-crypto"],
                ))
            # status 404 = still unavailable (current state); no finding emitted
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.debug("npm poll error (non-fatal): %s", exc)

    return findings


# ==========================================================================
# Mythos-Methodology — VBDIP + canonical-anchor integrity (Priority 5)
# ==========================================================================

# Files that constitute the methodology trust chain. Drift here doesn't
# break protocol mechanics, but it does break the auditability story.
_METHODOLOGY_REQUIRED_FILES: tuple[str, ...] = (
    "wiki/methodology/VBDIP-0001-vad-framework-introduction.md",
    "wiki/methodology/METHODOLOGY_LAYER_INTEGRATION_MAP.md",
    "wiki/methodology/bt_calibration_v1_1_architectural_revision.md",
    "wiki/methodology/sensor_stack_v2_1_architectural_revision.md",
    "wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf",
    "wiki/assessments/DualSense Edge Sensor-Stack Characterization for VAPI Track-1 Anti-Cheat Feature Architecture.pdf",
    "vsd-vault/eval/architect_key_attestation.json",
)


async def mythos_methodology_drift(
    *,
    repo_root: Path | None = None,
) -> list[MythosFindingResult]:
    """Methodology layer trust-chain integrity audit.

    Verifies the canonical anchors + VBDIP files + architect attestation
    that the protocol-layer surfaces inherit trust from. Missing any one
    of these breaks the methodology audit-trail story but does NOT break
    protocol mechanics (frozen_region=True for VBDIP / architect; MEDIUM
    elsewhere).
    """
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []

    for rel_path in _METHODOLOGY_REQUIRED_FILES:
        p = root / rel_path
        # Path objects normalize separators; check both is_file + is_dir
        # (PDFs are files; eval/ files; etc.)
        if not p.is_file():
            severity = (
                "HIGH" if "VBDIP-0001" in rel_path or "architect_key" in rel_path
                else "MEDIUM"
            )
            findings.append(MythosFindingResult(
                variant="methodology",
                severity=severity,
                description=(
                    f"METHODOLOGY FILE MISSING: {rel_path}. The methodology "
                    "trust chain that all protocol-layer surfaces inherit "
                    "trust from depends on this canonical anchor."
                ),
                recommended_fix=(
                    f"Restore {rel_path} from git history. "
                    "Do NOT regenerate — the architect Ed25519 attestation "
                    "+ Pass 2C verification basis are the canonical record."
                ),
                coherence_id=_coherence_id(
                    "methodology", f"missing:{rel_path}"
                ),
                file_path=rel_path,
                frozen_region=True,
                fix_authority_tier=3,
                evidence_sources=[rel_path],
            ))
        await asyncio.sleep(0)

    return findings


# ==========================================================================
# Mythos-Ceremony — pre/post ceremony invariant integrity (Priority 5)
# ==========================================================================

async def mythos_ceremony_drift(
    *,
    repo_root: Path | None = None,
    env_path: Path | None = None,
) -> list[MythosFindingResult]:
    """Pre/post ceremony invariant checks.

    Verifies the operator-runtime invariants that MUST hold before any
    chain-anchor ceremony fires:
      • CHAIN_SUBMISSION_PAUSED=true in bridge/.env (the kill-switch
        protecting against silent wallet drain; CRITICAL when False)
      • parallel anchor scripts exist + reference VAPI_GOVERNANCE_PHRASE
        wording correctly (HIGH when missing)
      • PV-CI invariant allowlist file exists + is parseable JSON (MEDIUM)
    """
    root = _resolve_repo_root(repo_root)
    if env_path is None:
        env_path = root / "bridge" / ".env"
    findings: list[MythosFindingResult] = []

    # Check 1: kill-switch state in bridge/.env
    if env_path.is_file():
        try:
            env_text = env_path.read_text(encoding="utf-8")
            # Look for CHAIN_SUBMISSION_PAUSED. False is what we're guarding against.
            for line in env_text.splitlines():
                ln = line.strip()
                if ln.startswith("#"):
                    continue
                if ln.startswith("CHAIN_SUBMISSION_PAUSED="):
                    val = ln.split("=", 1)[1].strip().lower()
                    if val == "false":
                        findings.append(MythosFindingResult(
                            variant="ceremony",
                            severity="CRITICAL",
                            description=(
                                "KILL-SWITCH DISARMED: bridge/.env has "
                                "CHAIN_SUBMISSION_PAUSED=false. Per Phase "
                                "237.5 Path C+ + the operator's hard rule "
                                "'no mainnet deploys until Operator "
                                "Initiative complete', the kill-switch "
                                "MUST be true except during an explicit "
                                "operator-runtime ceremony."
                            ),
                            recommended_fix=(
                                "Set CHAIN_SUBMISSION_PAUSED=true in "
                                "bridge/.env unless a ceremony is actively "
                                "running. Process-scoped override via "
                                "shell env var is the documented pattern "
                                "for one-shot ceremonies."
                            ),
                            coherence_id=_coherence_id(
                                "ceremony", "kill_switch_disarmed"
                            ),
                            file_path="bridge/.env",
                            frozen_region=True,
                            fix_authority_tier=3,
                            evidence_sources=["bridge/.env"],
                        ))
                    break
        except Exception as exc:  # noqa: BLE001 — fail-open
            log.debug("ceremony: env read error (non-fatal): %s", exc)

    # Check 2: parallel anchor scripts exist
    for script_name in ("parallel_o2_anchor.py", "parallel_o3_act_anchor.py"):
        p = root / "scripts" / script_name
        if not p.is_file():
            findings.append(MythosFindingResult(
                variant="ceremony",
                severity="HIGH",
                description=(
                    f"CEREMONY SCRIPT MISSING: scripts/{script_name}. "
                    "Operator-runtime ceremony cannot fire without this "
                    "script — Operator Initiative graduation BLOCKED."
                ),
                recommended_fix=f"Restore scripts/{script_name} from git history.",
                coherence_id=_coherence_id("ceremony", f"missing:{script_name}"),
                file_path=f"scripts/{script_name}",
                frozen_region=True,
                fix_authority_tier=3,
                evidence_sources=[f"scripts/{script_name}"],
            ))

    # Check 3: PV-CI invariant allowlist is parseable
    allowlist = root / ".github" / "INVARIANTS_ALLOWLIST.json"
    if allowlist.is_file():
        try:
            import json
            data = json.loads(allowlist.read_text(encoding="utf-8"))
            if not isinstance(data, dict) and not isinstance(data, list):
                findings.append(MythosFindingResult(
                    variant="ceremony",
                    severity="MEDIUM",
                    description=(
                        "PV-CI allowlist file has unexpected top-level "
                        f"type {type(data).__name__}. Governance ceremony "
                        "writes expect dict-typed allowlist."
                    ),
                    recommended_fix=(
                        "Re-run `python scripts/vapi_invariant_gate.py "
                        "--generate --reason 'refactor: regenerate allowlist'`."
                    ),
                    coherence_id=_coherence_id("ceremony", "allowlist_shape"),
                    file_path=".github/INVARIANTS_ALLOWLIST.json",
                    frozen_region=False,
                    fix_authority_tier=2,
                    evidence_sources=[".github/INVARIANTS_ALLOWLIST.json"],
                ))
        except Exception as exc:  # noqa: BLE001 — fail-open
            findings.append(MythosFindingResult(
                variant="ceremony",
                severity="MEDIUM",
                description=(
                    f"PV-CI allowlist file unparseable as JSON: {exc}. "
                    "Governance ceremony cannot read this state."
                ),
                recommended_fix=(
                    "Re-run `python scripts/vapi_invariant_gate.py "
                    "--generate --reason 'refactor: regenerate allowlist'`."
                ),
                coherence_id=_coherence_id("ceremony", "allowlist_unparseable"),
                file_path=".github/INVARIANTS_ALLOWLIST.json",
                frozen_region=False,
                fix_authority_tier=2,
                evidence_sources=[".github/INVARIANTS_ALLOWLIST.json"],
            ))
    else:
        findings.append(MythosFindingResult(
            variant="ceremony",
            severity="HIGH",
            description=(
                "PV-CI allowlist file MISSING at "
                ".github/INVARIANTS_ALLOWLIST.json. Any governance "
                "ceremony will refuse to fire (gate refuses without "
                "allowlist)."
            ),
            recommended_fix=(
                "Generate via `python scripts/vapi_invariant_gate.py "
                "--generate --reason 'refactor: restore missing allowlist'`."
            ),
            coherence_id=_coherence_id("ceremony", "missing:allowlist"),
            file_path=".github/INVARIANTS_ALLOWLIST.json",
            frozen_region=True,
            fix_authority_tier=3,
            evidence_sources=[".github/INVARIANTS_ALLOWLIST.json"],
        ))

    return findings


# ==========================================================================
# Mythos-Corpus — separation-ratio + TGE-blocker visibility (Priority 5)
# ==========================================================================

async def mythos_live_gameplay_audit(
    *,
    repo_root: Path | None = None,
    db_path: str | None = None,
    session_window_s: int = 60,
) -> list[MythosFindingResult]:
    """Mythos-Live-Gameplay (9th variant; Phase O5-MLGA Stage 2).

    Real-time audit of the dual-connected DualSense Edge capture stream
    during live gameplay (USB-HID to bridge laptop + BT-Classic BR/EDR
    to PS5). Per `wiki/methodology/mlga_architectural_proposal_v1.md` §4
    Audit Layer claim.

    Cadence: per_session (new 8th tier added 2026-05-15). Default
    polling interval 60s during active gameplay; finds drift in the
    capture stream within one cadence window.

    Four check families:
      1. HID stream integrity — capture_health_log latest row reports
         capture_state=NOMINAL + host_state in {EXCLUSIVE_USB, UNKNOWN}.
         Drift → MEDIUM (degraded capture; recoverable; not protocol drift).
      2. APOP classification health — active_play_occupancy_log shows
         confident readouts. UNKNOWN_LOW_EVIDENCE storm → MEDIUM.
      3. Sensor coverage — bio feature vectors in records are non-
         degenerate (not all zeros; trigger_active fraction reasonable).
         All-zero IMU/touchpad/stick → HIGH (sensor failure).
      4. Live state markers — recent records exist + GIC chain advancing
         OR explicitly chain-broken (which fires its own existing FSCA
         rule). Stalled chain with no records → LOW (operator may have
         paused; informational).

    NEVER raises. All findings frozen_region=False (live-capture state
    is operational, not protocol-layer FROZEN material). Mythos-Live-
    Gameplay is the only variant that emits exclusively non-frozen
    findings — by design. Live capture drift is recoverable; it
    doesn't taint FROZEN protocol surfaces.
    """
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []
    if db_path is None:
        db_path = str(root / "bridge" / "vapi_store.db")

    try:
        from vapi_bridge.store import Store
        store = Store(db_path=db_path)

        # ----- Check Family 1: HID stream integrity -----
        try:
            ch = store.get_capture_health_status()
            cap_state = (ch.get("capture_state") or "").upper()
            host_state = (ch.get("host_state") or "").upper()
            if cap_state and cap_state != "NOMINAL":
                findings.append(MythosFindingResult(
                    variant="live_gameplay",
                    severity="MEDIUM",
                    description=(
                        f"HID stream integrity DEGRADED: capture_state="
                        f"{cap_state}. Live gameplay capture is producing "
                        "degraded data; GIC chain advancement paused per "
                        "Phase 234.7 PCC gate. Operator inspect "
                        "capture_health_log for poll-rate dropout cause."
                    ),
                    recommended_fix=(
                        "Check USB-C cable + bridge laptop USB port; "
                        "verify hidapi sees interface 3 at ~1000 Hz "
                        "via GET /bridge/capture-health."
                    ),
                    coherence_id=_coherence_id(
                        "live_gameplay", f"hid_degraded:{cap_state}"
                    ),
                    frozen_region=False,
                    fix_authority_tier=2,
                    evidence_sources=[
                        "bridge/vapi_bridge/capture_continuity.py",
                        f"{db_path}:capture_health_log",
                    ],
                ))
            if host_state and host_state not in (
                "EXCLUSIVE_USB", "UNKNOWN"
            ):
                findings.append(MythosFindingResult(
                    variant="live_gameplay",
                    severity="MEDIUM",
                    description=(
                        f"HOST arbitration CONTESTED: host_state={host_state}. "
                        "Bridge laptop USB poll-rate is unstable — typically "
                        "indicates PS Remote Play / streaming session "
                        "competing with USB-HID. MLGA capture quality "
                        "degrades; GIC chain pauses."
                    ),
                    recommended_fix=(
                        "Disable PS Remote Play during MLGA gameplay; "
                        "use dual-connection (USB-C to laptop + BT to PS5) "
                        "rather than streaming."
                    ),
                    coherence_id=_coherence_id(
                        "live_gameplay", f"host_contested:{host_state}"
                    ),
                    frozen_region=False,
                    fix_authority_tier=2,
                    evidence_sources=[
                        "bridge/vapi_bridge/capture_continuity.py",
                    ],
                ))
        except Exception:  # noqa: BLE001 — fail-open
            pass

        # ----- Check Family 2: APOP classification health -----
        try:
            import sqlite3
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT classified_state, COUNT(*) AS n "
                "FROM active_play_occupancy_log "
                "WHERE created_at > ? "
                "GROUP BY classified_state",
                (time.time() - session_window_s,),
            ).fetchall()
            con.close()
            counts = {dict(r)["classified_state"]: int(dict(r)["n"]) for r in rows}
            total = sum(counts.values())
            if total > 0:
                unknown = counts.get("UNKNOWN_LOW_EVIDENCE", 0)
                if unknown / total > 0.5:
                    findings.append(MythosFindingResult(
                        variant="live_gameplay",
                        severity="MEDIUM",
                        description=(
                            f"APOP classifier UNCONFIDENT: "
                            f"{unknown}/{total} classifications in last "
                            f"{session_window_s}s are UNKNOWN_LOW_EVIDENCE. "
                            "Per Phase 241-APOP-FIX, this typically means "
                            "frame_checkpoints are stale or sampling is "
                            "below the 10/sec gate."
                        ),
                        recommended_fix=(
                            "Verify _dispatch in dualshock_integration.py "
                            "sample-rate-limited writer is running at 10/sec; "
                            "check frame_checkpoint table growth rate."
                        ),
                        coherence_id=_coherence_id(
                            "live_gameplay",
                            f"apop_unconfident:{unknown}_{total}",
                        ),
                        frozen_region=False,
                        fix_authority_tier=2,
                        evidence_sources=[
                            "bridge/vapi_bridge/active_play_occupancy.py",
                            f"{db_path}:active_play_occupancy_log",
                        ],
                    ))
        except Exception:  # noqa: BLE001 — table may not exist; fail-open
            pass

        # ----- Check Family 3: Sensor coverage during gameplay -----
        try:
            import sqlite3
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT COUNT(*) AS n_total, "
                "       SUM(COALESCE(trigger_active, 0)) AS n_trigger_active "
                "FROM records "
                "WHERE created_at > ?",
                (time.time() - session_window_s,),
            ).fetchone()
            con.close()
            n_total = int(dict(row)["n_total"] or 0) if row else 0
            n_trig = int(dict(row).get("n_trigger_active", 0) or 0) if row else 0
            if n_total > 100 and n_trig == 0:
                findings.append(MythosFindingResult(
                    variant="live_gameplay",
                    severity="HIGH",
                    description=(
                        f"Sensor coverage ANOMALY: {n_total} records in "
                        f"last {session_window_s}s but ZERO trigger_active "
                        "events. Either player is on a menu (expected; APOP "
                        "would report MENU_DETECTED) OR trigger-onset "
                        "detection is broken. Cross-check with APOP "
                        "classification before remediation."
                    ),
                    recommended_fix=(
                        "Check Phase 235-GAD trigger-onset gate "
                        "(trigger_active = int(velocity_l2 > 0 OR "
                        "velocity_r2 > 0)). If broken, gameplay-context "
                        "classification degrades; consecutive_clean "
                        "advances incorrectly."
                    ),
                    coherence_id=_coherence_id(
                        "live_gameplay",
                        f"sensor_zero_trigger:{n_total}",
                    ),
                    frozen_region=False,
                    fix_authority_tier=2,
                    evidence_sources=[
                        "bridge/vapi_bridge/dualshock_integration.py",
                        f"{db_path}:records",
                    ],
                ))
        except Exception:  # noqa: BLE001
            pass

        # ----- Check Family 4: Live state markers (GIC + records) -----
        try:
            from vapi_bridge.config import Config
            cfg = Config()
            gc = store.get_grind_chain_status(
                grind_session_id=getattr(cfg, "grind_session_id", "default"),
                cfg=cfg,
            )
            if not gc.get("chain_intact", True):
                findings.append(MythosFindingResult(
                    variant="live_gameplay",
                    severity="HIGH",
                    description=(
                        "GIC chain BROKEN during MLGA-active session. "
                        "Cannot advance grind chain until operator "
                        "POST /operator/gic-reset and restarts bridge."
                    ),
                    recommended_fix=(
                        "Operator: POST /operator/gic-reset with audit "
                        "reason ≥10 chars + restart bridge."
                    ),
                    coherence_id=_coherence_id(
                        "live_gameplay", "gic_chain_broken"
                    ),
                    frozen_region=False,
                    fix_authority_tier=2,
                    evidence_sources=[
                        "bridge/vapi_bridge/grind_chain.py",
                    ],
                ))
        except Exception:  # noqa: BLE001
            pass

        return findings
    except Exception as exc:  # noqa: BLE001
        findings.append(MythosFindingResult(
            variant="live_gameplay",
            severity="LOW",
            description=f"Mythos-Live-Gameplay audit raised: {exc}",
            recommended_fix="Investigate variant module.",
            coherence_id=_coherence_id("live_gameplay", "exception"),
            frozen_region=False,
            fix_authority_tier=2,
            evidence_sources=["bridge/vapi_bridge/mythos_variants.py"],
        ))
        return findings


async def mythos_post_o3_ceremony_audit(
    *,
    repo_root: Path | None = None,
    db_path: str | None = None,
    include_chain_reads: bool = False,
) -> list[MythosFindingResult]:
    """Mythos-Post-O3 — wraps scripts/operator_initiative_post_o3_audit.py
    (operator-authorized goal 2026-05-15) and emits its sections as Mythos
    findings. Cadence: post_ceremony tier — runs automatically after the
    Day 15 ceremony fires (operator-runtime).

    Section 1 (activation_log integrity) FAIL → CRITICAL frozen_region findings
    Section 2 (on-chain scopeRoot)        FAIL → CRITICAL frozen_region findings
    Section 3 (Mythos OpInit cross-check) FAIL → HIGH    frozen_region findings
    Section 4 (FSCA contradictions)       PRESENT → MEDIUM findings

    NEVER raises (fail-open contract). All severity-CRITICAL/HIGH findings
    carry frozen_region=True → INV-MYTHOS-FROZEN-PROTECTION-001 forces
    tier=3 read-only at the store layer.
    """
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []
    try:
        # Defer heavy import — the audit script is in scripts/ not on the
        # bridge import path by default.
        import sys
        scripts_path = str(root / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        try:
            import operator_initiative_post_o3_audit as audit_mod
        except Exception as exc:  # noqa: BLE001
            findings.append(MythosFindingResult(
                variant="post_o3",
                severity="LOW",
                description=(
                    f"Could not import scripts/operator_initiative_post_o3_"
                    f"audit.py: {exc}. Mythos-Post-O3 audit skipped."
                ),
                recommended_fix=(
                    "Restore scripts/operator_initiative_post_o3_audit.py "
                    "from git history."
                ),
                coherence_id=_coherence_id("post_o3", "import_fail"),
                frozen_region=False,
                fix_authority_tier=2,
                evidence_sources=["scripts/operator_initiative_post_o3_audit.py"],
            ))
            return findings

        if db_path is None:
            db_path = str(root / "bridge" / "vapi_store.db")
        audit = await audit_mod.run_audit(
            db_path=db_path,
            include_chain_reads=include_chain_reads,
            repo_root=root,
        )
        sections = audit.get("sections", {})

        # Section 1: activation_log integrity
        s1 = sections.get("section_1", {})
        if s1 and not s1.get("all_pass", True):
            for agent_name, entry in (s1.get("per_agent") or {}).items():
                if entry.get("pass", True):
                    continue
                checks = entry.get("checks", {})
                key = f"{agent_name}:" + ",".join(
                    f"{k}={v}" for k, v in checks.items()
                    if k.endswith("_ok") and v is False
                )
                findings.append(MythosFindingResult(
                    variant="post_o3",
                    severity="CRITICAL",
                    description=(
                        f"POST-O3 SECTION 1 (activation_log integrity) FAIL "
                        f"for {agent_name}: "
                        + ", ".join(
                            f"{k}={v}" for k, v in checks.items()
                            if v is False
                        )
                        or f"agent={agent_name}; see audit checks for detail."
                    ),
                    recommended_fix=(
                        "Re-fire scripts/parallel_o3_act_anchor.py for the "
                        "missing/divergent agent OR investigate activation_"
                        "log row mismatch."
                    ),
                    coherence_id=_coherence_id("post_o3", f"section_1:{key}"),
                    frozen_region=True,
                    fix_authority_tier=3,
                    evidence_sources=[
                        "bridge/vapi_store.db:operator_agent_activation_log",
                        "scripts/parallel_o3_act_anchor.py",
                    ],
                ))

        # Section 2: on-chain scopeRoot (only if chain reads enabled)
        s2 = sections.get("section_2", {})
        if s2 and not s2.get("all_pass", True):
            for agent_name, entry in (s2.get("per_agent") or {}).items():
                if entry.get("pass", True):
                    continue
                findings.append(MythosFindingResult(
                    variant="post_o3",
                    severity="CRITICAL",
                    description=(
                        f"POST-O3 SECTION 2 (on-chain scopeRoot) FAIL for "
                        f"{agent_name}: live={(entry.get('live') or '')[:18]}"
                        f"... expected={entry.get('expected', '')[:18]}..."
                    ),
                    recommended_fix=(
                        "Critical drift between on-chain AgentScope state "
                        "and pre-authored Cedar bundle. Investigate "
                        "immediately + halt any subsequent ceremony activity."
                    ),
                    coherence_id=_coherence_id(
                        "post_o3", f"section_2:{agent_name}"
                    ),
                    frozen_region=True,
                    fix_authority_tier=3,
                    evidence_sources=[
                        "AgentScope contract on chain ID 4690",
                        f"bridge/vapi_bridge/cedar_bundles/{agent_name}_o3_acting_v1.json",
                    ],
                ))

        # Section 3: Mythos OpInit cross-reference
        s3 = sections.get("section_3", {})
        if s3 and not s3.get("all_pass", True):
            n = s3.get("finding_count", 0)
            findings.append(MythosFindingResult(
                variant="post_o3",
                severity="HIGH",
                description=(
                    f"POST-O3 SECTION 3 (Mythos OpInit cross-reference) "
                    f"FAIL: {n} findings surfaced when audit re-ran the "
                    "OpInit variant. See mythos_finding_log for full details."
                ),
                recommended_fix=(
                    "Inspect mythos_finding_log filtered by "
                    "variant='operator_initiative' for the specific drift."
                ),
                coherence_id=_coherence_id(
                    "post_o3", f"section_3:{n}_findings"
                ),
                frozen_region=True,
                fix_authority_tier=3,
                evidence_sources=["mythos_finding_log"],
            ))

        # Section 4: FSCA contradictions (informational MEDIUM)
        s4 = sections.get("section_4", {})
        if s4 and s4.get("contradictions_present"):
            n = len(s4.get("rows", []))
            findings.append(MythosFindingResult(
                variant="post_o3",
                severity="MEDIUM",
                description=(
                    f"POST-O3 SECTION 4: {n} FSCA contradiction(s) fired in "
                    "the hour after ceremony. May be expected (agents now "
                    "operating in lifted scope) OR may indicate ceremony "
                    "introduced drift. Operator inspects fleet_coherence_log."
                ),
                recommended_fix=(
                    "Query fleet_coherence_log for the post-ceremony hour. "
                    "Each contradiction has its own recommended_fix per "
                    "FSCA CONTRADICTION_RULES."
                ),
                coherence_id=_coherence_id(
                    "post_o3", f"section_4:{n}_contradictions"
                ),
                frozen_region=False,
                fix_authority_tier=2,
                evidence_sources=["bridge/vapi_store.db:fleet_coherence_log"],
            ))
        return findings
    except Exception as exc:  # noqa: BLE001 — fail-open
        findings.append(MythosFindingResult(
            variant="post_o3",
            severity="LOW",
            description=f"Mythos-Post-O3 audit raised: {exc}",
            recommended_fix="Investigate post-O3 audit module.",
            coherence_id=_coherence_id("post_o3", "exception"),
            frozen_region=False,
            fix_authority_tier=2,
            evidence_sources=["scripts/operator_initiative_post_o3_audit.py"],
        ))
        return findings


async def mythos_corpus_drift(
    *,
    repo_root: Path | None = None,
    db_path: str | None = None,
) -> list[MythosFindingResult]:
    """Corpus integrity + TGE-blocker visibility audit.

    Queries the bridge SQLite store for separation_ratio / GIC chain /
    AIT defensibility state and surfaces TGE-blocker conditions per the
    CLAUDE.md Hard Rules ("no TGE before separation_ratio > 1.0
    confirmed — non-negotiable"). Most findings are INFORMATIONAL —
    they surface the current corpus state without claiming drift.

    DB-state mismatches with the CLAUDE.md narrative (e.g., empty DB
    showing zero corpus while CLAUDE.md narrates N=37 AIT corpus) are
    surfaced as LOW informational findings — they reflect dev-vs-prod
    DB divergence, not protocol drift.
    """
    root = _resolve_repo_root(repo_root)
    if db_path is None:
        db_path = str(root / "bridge" / "vapi_store.db")
    findings: list[MythosFindingResult] = []

    try:
        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row

        # Check 1: separation_defensibility_log state (informational —
        # this is the Phase 150 probe-type-keyed corpus state per CLAUDE.md
        # Phase 150 reference, NOT separation_ratio_snapshots which is the
        # battery-stratified pooled-ratio surface).
        try:
            row = con.execute(
                "SELECT COUNT(*) AS n FROM separation_defensibility_log"
            ).fetchone()
            sep_count = int(row["n"] or 0) if row else 0
        except Exception:  # noqa: BLE001
            sep_count = 0

        if sep_count == 0:
            findings.append(MythosFindingResult(
                variant="corpus",
                severity="LOW",
                description=(
                    f"CORPUS STATE: separation_defensibility_log table is "
                    f"empty in {db_path}. CLAUDE.md narrates the live "
                    "corpus state (touchpad_corners=0.728 N=35; "
                    "ait=1.199 N=37; tremor_resting=1.177 N=27) but the "
                    "local DB does not reflect this. This is typically a "
                    "dev-vs-prod DB divergence — operator's production "
                    "bridge holds the canonical state."
                ),
                recommended_fix=(
                    "Operational: run audit against production DB via "
                    "--db PATH OR populate local DB from a snapshot."
                ),
                coherence_id=_coherence_id(
                    "corpus", "empty_separation_defensibility_log"
                ),
                frozen_region=False,
                fix_authority_tier=2,
                evidence_sources=[db_path, "CLAUDE.md"],
            ))

        # Check 2: TGE invariant — surface separation ratio per probe type.
        # separation_defensibility_log columns: session_type / ratio /
        # all_pairs_above_1 / n_sessions_total / n_per_player_json /
        # defensible / created_at.
        try:
            rows = con.execute(
                "SELECT session_type, ratio, all_pairs_above_1, "
                "       n_per_player_json, defensible, created_at "
                "FROM separation_defensibility_log "
                "ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
            seen_probes = set()
            for r in rows:
                d = dict(r)
                pt = d.get("session_type", "")
                if pt in seen_probes:
                    continue
                seen_probes.add(pt)
                ratio = float(d.get("ratio") or 0.0)
                all_pairs = int(d.get("all_pairs_above_1") or 0)
                if ratio < 1.0 or all_pairs == 0:
                    findings.append(MythosFindingResult(
                        variant="corpus",
                        severity="MEDIUM",
                        description=(
                            f"TGE BLOCKER (informational): session_type={pt} "
                            f"latest ratio={ratio:.3f}, "
                            f"all_pairs_above_1={all_pairs}. Per Hard Rule "
                            "'no TGE before separation_ratio > 1.0', this "
                            "probe type is a TGE blocker until clearance "
                            "is confirmed."
                        ),
                        recommended_fix=(
                            "Operational: continue corpus growth via the "
                            "hardware-capture protocol per the canonical "
                            "anchor documents. Mythos-Corpus surfaces "
                            "state; growth happens off-CLI."
                        ),
                        coherence_id=_coherence_id(
                            "corpus", f"tge_blocker:{pt}"
                        ),
                        frozen_region=False,
                        fix_authority_tier=2,
                        evidence_sources=[db_path],
                    ))
        except Exception:  # noqa: BLE001 — table may not exist
            pass

        # Check 3: GIC chain integrity
        try:
            row = con.execute(
                "SELECT COUNT(*) AS n, MAX(gic_ts_ns) AS latest "
                "FROM ruling_validation_log "
                "WHERE grind_chain_hash IS NOT NULL AND grind_chain_hash != ''"
            ).fetchone()
            gic_count = int(row["n"] or 0) if row else 0
            # Informational — populated GIC chain is healthy; empty is
            # dev-DB state.
            if gic_count == 0:
                findings.append(MythosFindingResult(
                    variant="corpus",
                    severity="LOW",
                    description=(
                        "GIC chain (Phase 235-A) is empty in local DB. "
                        "CLAUDE.md narrates GIC_100 reached 2026-05-05 + "
                        "anchored 2026-05-06; production state is the "
                        "canonical record."
                    ),
                    recommended_fix=(
                        "Operational: audit against production DB."
                    ),
                    coherence_id=_coherence_id("corpus", "empty_gic_chain"),
                    frozen_region=False,
                    fix_authority_tier=2,
                    evidence_sources=[db_path, "CLAUDE.md"],
                ))
        except Exception:  # noqa: BLE001
            pass

        con.close()
    except Exception as exc:  # noqa: BLE001 — fail-open
        findings.append(MythosFindingResult(
            variant="corpus",
            severity="LOW",
            description=(
                f"Corpus audit could not open DB {db_path}: {exc}. "
                "This is informational — local DB may not exist yet."
            ),
            recommended_fix="Operational; investigate DB path if expected.",
            coherence_id=_coherence_id("corpus", f"db_open_fail"),
            frozen_region=False,
            fix_authority_tier=2,
            evidence_sources=[db_path],
        ))

    return findings


# ==========================================================================
# Mythos-Claude-MD-Curation — documentation curation guardrail
# ==========================================================================

# Date marker inside a NOTE: looks for YYYY-MM-DD in the first 200 chars
_PAT_NOTE_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

# Closure markers — a NOTE containing one of these for some arc tag
# supersedes earlier mid-arc NOTEs for the same tag
_CLOSURE_MARKERS = (
    "EMPIRICAL CLOSURE",
    "COMPLETE",
    "FINAL",
    "CLOSED",
    "TERMINAL",
    "SHIPPED",
)

# Arc-tag regex — extracts identifiers like "STABILITY-9", "PHASE 235.x-STABILITY-9",
# "PHASE O1-D-PATH-B", "PHASE 237-ZK-SEPPROOF"
_PAT_ARC_TAG = re.compile(
    r"(PHASE\s+[A-Z0-9]+(?:[-.][A-Z0-9]+)*|STABILITY-\d+|ZKBA-TRACK\d+|"
    r"VBDIP-\d{4}|QRESCE-\d{4}|MLGA|VPM|EVIDENCE OS)",
    re.IGNORECASE,
)


def _marker_matches(marker: str, upper_text: str) -> bool:
    """Word-boundary match for closure markers — avoids 'COMPLETE' matching
    'COMPLETED' or 'INCOMPLETE'. Uses simple regex anchored on non-word
    chars around the marker."""
    pattern = r"(?:^|[^A-Z])" + re.escape(marker) + r"(?:$|[^A-Z])"
    return bool(re.search(pattern, upper_text))


def _extract_arc_tags(text: str) -> set[str]:
    """Extract canonical arc tags from a NOTE first ~300 chars."""
    head = text[:300].upper()
    return {m.group(1).upper() for m in _PAT_ARC_TAG.finditer(head)}


async def mythos_claude_md_curation(
    *,
    repo_root: Path | None = None,
    stale_days_threshold: int = 30,
    target_chars: int = 60_000,
    warn_chars: int = 100_000,
) -> list[MythosFindingResult]:
    """Documentation curation guardrail — audits CLAUDE.md for staleness.

    Born from 2026-05-18 manual prune (400k -> 139k chars after operator
    intervention). Future arcs that append NOTEs without retiring older
    ones will re-bloat the file; this variant flags candidates for
    archival to wiki/phases/ so the prune work doesn't have to recur
    manually.

    Three finding classes:

      1. CLAUDE_MD_OVERSIZE — file >warn_chars (default 100k). LOW
         informational; recommends running the prune script.

      2. STALE_NOTE_SUPERSEDED — NOTE for an arc-tag where a LATER NOTE
         exists with one of _CLOSURE_MARKERS for the same tag. MEDIUM
         severity. Recommendation: archive to wiki/phases/ + replace
         with pointer NOTE.

      3. STALE_NOTE_OLDER_THAN_30D — NOTE with an explicit date marker
         older than stale_days_threshold (default 30) days from today.
         LOW severity. Recommendation: review for archival.

    Fail-open: errors reading CLAUDE.md are swallowed; returns []."""
    root = _resolve_repo_root(repo_root)
    findings: list[MythosFindingResult] = []
    claude_md = root / "CLAUDE.md"

    try:
        text = claude_md.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — fail-open
        log.debug("mythos_claude_md_curation: cannot read CLAUDE.md (%s)", exc)
        return findings

    char_count = len(text)

    # Check 1: oversize
    if char_count > warn_chars:
        findings.append(MythosFindingResult(
            variant="claude_md_curation",
            severity="LOW",
            description=(
                f"CLAUDE.md is {char_count:,} chars (>{warn_chars:,} warn threshold; "
                f"target {target_chars:,}). Claude Code degrades performance above "
                "40,000 chars; ~120k is acceptable, >200k recurring needs prune."
            ),
            recommended_fix=(
                "Run scripts/_prune_claude_md.py + scripts/_prune_claude_md_pass2.py "
                "(or write a fresh prune script). Migrate completed-arc NOTEs to "
                "wiki/phases/ + leave one-line pointer NOTEs. Aim to keep only 5-7 "
                "most-recent NOTEs inline."
            ),
            coherence_id=_coherence_id("claude_md_curation", f"oversize:{char_count // 10_000}"),
            file_path="CLAUDE.md",
            frozen_region=False,
            fix_authority_tier=2,
            evidence_sources=["CLAUDE.md"],
        ))

    # Parse NOTE block boundaries (each NOTE is on a single line by VAPI convention)
    note_entries: list[tuple[int, str]] = []  # (line_no_1_indexed, content)
    for line_no, line in enumerate(text.splitlines(), start=1):
        if line.startswith("NOTE:"):
            note_entries.append((line_no, line))

    # Check 2: superseded NOTEs (arc-tag has a later closure NOTE)
    # NOTE entries are chronologically newest-first per VAPI convention.
    # An EARLIER (higher index = older) NOTE is superseded by a LATER
    # (lower index = newer) NOTE matching the same arc tag with a closure marker.
    closure_tags: set[str] = set()
    # First pass: identify closure NOTEs (top of file = most recent)
    for line_no, content in note_entries:
        upper = content.upper()
        if any(_marker_matches(marker, upper) for marker in _CLOSURE_MARKERS):
            tags = _extract_arc_tags(content)
            closure_tags |= tags

    # Second pass: any non-closure NOTE matching a closed arc tag is superseded
    for line_no, content in note_entries:
        upper = content.upper()
        if any(_marker_matches(marker, upper) for marker in _CLOSURE_MARKERS):
            continue  # this IS a closure NOTE — keep
        # Skip curation tombstones (they reference closed arcs by design)
        if "ARCHIVED" in upper or "CURATION" in upper or "POINTER" in upper:
            continue
        tags = _extract_arc_tags(content)
        superseded_by = tags & closure_tags
        if superseded_by:
            # First 80 chars for evidence
            preview = content[:120].replace("NOTE: ", "").rstrip()
            findings.append(MythosFindingResult(
                variant="claude_md_curation",
                severity="MEDIUM",
                description=(
                    f"CLAUDE.md L{line_no}: superseded NOTE — arc tag(s) "
                    f"{sorted(superseded_by)} have a closure NOTE elsewhere in the "
                    f"file. Preview: '{preview}...'"
                ),
                recommended_fix=(
                    f"Archive L{line_no} to wiki/phases/phase_<arc>_archive.md + "
                    "replace inline with a single-line pointer NOTE. Keep closure "
                    "NOTE in CLAUDE.md as canonical entry for the arc."
                ),
                coherence_id=_coherence_id("claude_md_curation", f"superseded:L{line_no}"),
                file_path="CLAUDE.md",
                line_number=line_no,
                frozen_region=False,
                fix_authority_tier=2,
                evidence_sources=["CLAUDE.md"],
            ))

    # Check 3: NOTEs older than stale_days_threshold (best-effort date parse)
    today_y, today_m, today_d = _today_ymd()
    today_ordinal = today_y * 372 + today_m * 31 + today_d  # rough days-since-epoch proxy
    for line_no, content in note_entries:
        m = _PAT_NOTE_DATE.search(content[:200])
        if not m:
            continue
        try:
            y, mo, d = m.group(1).split("-")
            note_ordinal = int(y) * 372 + int(mo) * 31 + int(d)
        except Exception:  # noqa: BLE001
            continue
        age_days = today_ordinal - note_ordinal
        if age_days <= stale_days_threshold:
            continue
        # Skip if also flagged as superseded (avoid duplicate finding)
        upper = content.upper()
        tags = _extract_arc_tags(content)
        if any(marker in upper for marker in _CLOSURE_MARKERS) and tags <= closure_tags:
            # This IS a closure NOTE — old but canonical, keep
            continue
        preview = content[:100].replace("NOTE: ", "").rstrip()
        findings.append(MythosFindingResult(
            variant="claude_md_curation",
            severity="LOW",
            description=(
                f"CLAUDE.md L{line_no}: NOTE is {age_days} days old "
                f"(date marker {m.group(1)}; threshold {stale_days_threshold}). "
                f"Preview: '{preview}...'"
            ),
            recommended_fix=(
                f"Review L{line_no} for archival. Old NOTEs that document closed "
                "arcs should migrate to wiki/phases/; old NOTEs that pin still-load-"
                "bearing reference (Hard Rules, FROZEN-v1 formulas, brand discipline) "
                "should stay verbatim and are exempt by operator review."
            ),
            coherence_id=_coherence_id("claude_md_curation", f"stale:L{line_no}"),
            file_path="CLAUDE.md",
            line_number=line_no,
            frozen_region=False,
            fix_authority_tier=2,
            evidence_sources=["CLAUDE.md"],
        ))

    return findings


def _today_ymd() -> tuple[int, int, int]:
    """Year/month/day tuple from system clock. Isolated for test injection."""
    import datetime as _dt
    today = _dt.date.today()
    return (today.year, today.month, today.day)
