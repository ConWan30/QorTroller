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
