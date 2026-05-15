"""Phase O5-MYTHOS-MINIMAL M.2 — Mythos variant implementations.

Two variants ship in the minimal-Mythos arc per the approved plan. Each is
a deterministic, fail-open async function that returns a list of
MythosFindingResult. The cadence engine (M.1) invokes them via
get_pending_variants(); the MCP tool layer (this commit also extends
vapi-mcp/unified_server.py) wraps them as `vapi_mythos_frozen_drift` and
`vapi_mythos_stability_sweep` for operator-runtime invocation.

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
