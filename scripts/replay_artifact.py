"""Reproducibility Receipt — external verifier for ZKBA + VPM artifacts.

Extends the FROZEN deterministic compiler invariant (INV-VPM-COMPILER-001,
INV-ZKBA-003) from an asserted property to a publicly-executable
verification surface. An external reviewer holding only the manifest +
the on-disk HTML + the public source of this script can independently
verify that:

  1. The manifest's `schema` matches one of the FROZEN schema strings
     (`vapi-zkba-manifest-v1` or `vapi-vpm-artifact-v1`).
  2. Every structural field has the expected type and shape.
  3. The artifact HTML file exists at the path declared by the manifest.
  4. `SHA-256(html_bytes_on_disk) == manifest.output_hash_hex`.
  5. For VPM artifacts, the emitted HTML passes the same Layer 2 visual
     grammar checks the bridge audit pass runs (Anti-Hype Visual Grammar
     compile-time guards re-executed against the on-disk artifact).

No bridge DB. No bridge HTTP. No network. No wallet. Pure stdlib + the
project's existing FROZEN compiler module.

Closing the "external reviewer cannot independently verify an artifact"
gap is the protocol's structural answer to demo-as-production /
revoked-as-active / unverified-as-verified overclaim attacks. Phase O4's
three-layer Anti-Hype Visual Grammar enforces grammar at compile / audit
/ browser time. This receipt closes the loop by making the COMPILE-TIME
claim independently re-checkable after artifact emission, without
trusting the protocol's runtime.

Run:

    # Verify a single ZKBA artifact's manifest+HTML pair:
    python scripts/replay_artifact.py path/to/<commit>.manifest.json

    # Verify all artifacts under a directory:
    python scripts/replay_artifact.py --dir frontend/src/artifacts/hardware_participation_card

    # Emit machine-readable JSON instead of human report:
    python scripts/replay_artifact.py path/to/<commit>.manifest.json --json

Exit codes:
  0  All artifacts verified PASS
  1  One or more artifacts FAIL output_hash mismatch
  2  One or more artifacts FAIL manifest structural validation
  3  One or more artifacts FAIL Layer 2 visual grammar (VPM only)
  4  Configuration / file-access error

Author: VAPI Architect — Reproducibility Receipt ships 2026-05-13 per
operator authorization. Extends the FROZEN deterministic-compile invariant
into the publicly-actionable verification surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# FROZEN schema strings — must match _MANIFEST_SCHEMA + _VPM_ARTIFACT_SCHEMA
# in scripts/vsd_ui_compiler.py exactly.
ZKBA_SCHEMA = "vapi-zkba-manifest-v1"
VPM_SCHEMA = "vapi-vpm-artifact-v1"

# Required structural fields per schema. Catches manifest-truncation /
# forgery attempts that produce a partially-populated manifest.
ZKBA_REQUIRED_FIELDS = (
    "schema",
    "zkba_class",
    "proof_weight",
    "output_path",
    "output_hash_hex",
    "input_commitment_hex",
    "compiler_version",
    "ts_ns",
)
VPM_REQUIRED_FIELDS = (
    "schema",
    "vpm_id",
    "zkba_class",
    "proof_weight",
    "visual_state",
    "capture_mode",
    "integrity_label_hash_hex",
    "wrapper_schema",
    "zkba_manifest_hash_hex",
    "output_path",
    "output_hash_hex",
    "input_commitment_hex",
    "compiler_version",
    "ts_ns",
)


@dataclass(slots=True)
class CheckResult:
    """Per-artifact verification result."""
    manifest_path: str = ""
    schema_form: str = ""
    structural_ok: bool = False
    structural_errors: list[str] = field(default_factory=list)
    html_path_resolved: str = ""
    html_present: bool = False
    output_hash_claimed: str = ""
    output_hash_computed: str = ""
    output_hash_match: bool = False
    visual_grammar_ok: bool = True  # default True; only VPM exercises Layer 2
    visual_grammar_violations: list[str] = field(default_factory=list)
    overall_verdict: str = "UNKNOWN"


def _hex64(value: object) -> bool:
    """Validate a 64-char lowercase hex string (SHA-256 output)."""
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _validate_structural(manifest: dict) -> tuple[str, list[str]]:
    """Return (schema_form, errors). schema_form is "" if unrecognized."""
    errors: list[str] = []
    schema = manifest.get("schema")
    if schema == ZKBA_SCHEMA:
        required = ZKBA_REQUIRED_FIELDS
        form = "zkba"
    elif schema == VPM_SCHEMA:
        required = VPM_REQUIRED_FIELDS
        form = "vpm"
    else:
        return "", [f"unknown schema: {schema!r}"]

    for field_name in required:
        if field_name not in manifest:
            errors.append(f"missing required field: {field_name}")

    # Type / shape checks
    if "output_hash_hex" in manifest and not _hex64(manifest["output_hash_hex"]):
        errors.append("output_hash_hex must be 64-char lowercase hex")
    if "input_commitment_hex" in manifest and not _hex64(
        manifest["input_commitment_hex"]
    ):
        errors.append("input_commitment_hex must be 64-char lowercase hex")
    ts_ns = manifest.get("ts_ns")
    if ts_ns is not None and not (
        isinstance(ts_ns, int) and 0 <= ts_ns <= (2**64 - 1)
    ):
        errors.append("ts_ns must be a uint64")
    zc = manifest.get("zkba_class")
    if zc is not None and not (isinstance(zc, int) and 1 <= zc <= 7):
        errors.append("zkba_class must be int in 1..7")
    pw = manifest.get("proof_weight")
    if pw is not None and not (isinstance(pw, int) and 1 <= pw <= 6):
        errors.append("proof_weight must be int in 1..6")

    if form == "vpm":
        if manifest.get("schema") != VPM_SCHEMA:
            errors.append(
                f"schema must be {VPM_SCHEMA!r} for VPM form"
            )
        if "zkba_manifest_hash_hex" in manifest and not _hex64(
            manifest["zkba_manifest_hash_hex"]
        ):
            errors.append("zkba_manifest_hash_hex must be 64-char lowercase hex")
        if "integrity_label_hash_hex" in manifest and not _hex64(
            manifest["integrity_label_hash_hex"]
        ):
            errors.append(
                "integrity_label_hash_hex must be 64-char lowercase hex"
            )

    return form, errors


def _resolve_html_path(
    manifest_path: Path, output_path_field: str
) -> Path:
    """Resolve the on-disk HTML path. Manifest declares output_path as
    POSIX-style under output_dir; we resolve relative to the manifest's
    directory."""
    candidate = Path(output_path_field)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    # Try sibling of manifest (the common case — compiler writes
    # <commit>.html + <commit>.manifest.json side-by-side).
    sibling = manifest_path.parent / candidate.name
    if sibling.exists():
        return sibling
    # Try resolving the full output_path relative to manifest's parent.
    rel = manifest_path.parent / candidate
    return rel


def _compute_html_hash(html_path: Path) -> str:
    """SHA-256 of the HTML file bytes."""
    h = hashlib.sha256()
    with html_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_visual_grammar(html_body: str) -> list[str]:
    """Layer 2 visual grammar check — re-run the FROZEN compiler-side
    guards against the on-disk HTML. Returns empty list on PASS."""
    try:
        from vsd_ui_compiler import (  # type: ignore
            VPMComplianceError,
            _enforce_vpm_compiler_discipline,
            _verify_integrity_label_in_dom,
        )
    except ImportError as exc:
        return [f"vsd_ui_compiler not importable: {exc}"]

    violations: list[str] = []
    try:
        _enforce_vpm_compiler_discipline(html_body)
    except VPMComplianceError as exc:
        violations.append(f"compiler_discipline: {exc}")
    try:
        _verify_integrity_label_in_dom(html_body)
    except VPMComplianceError as exc:
        violations.append(f"integrity_label_dom: {exc}")
    return violations


def verify_manifest(manifest_path: Path) -> CheckResult:
    """Verify a single manifest+HTML pair. Never raises; returns CheckResult."""
    result = CheckResult(manifest_path=str(manifest_path))

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        result.structural_errors.append(f"manifest unreadable: {exc}")
        result.overall_verdict = "FAIL_STRUCTURAL"
        return result

    form, structural_errors = _validate_structural(manifest)
    result.schema_form = form
    result.structural_errors = structural_errors
    result.structural_ok = (form != "" and len(structural_errors) == 0)

    if not result.structural_ok:
        result.overall_verdict = "FAIL_STRUCTURAL"
        return result

    output_path_field = manifest["output_path"]
    html_path = _resolve_html_path(manifest_path, output_path_field)
    result.html_path_resolved = str(html_path)
    result.html_present = html_path.exists()

    if not result.html_present:
        result.structural_errors.append(
            f"HTML file not found at resolved path: {html_path}"
        )
        result.overall_verdict = "FAIL_STRUCTURAL"
        return result

    try:
        html_body = html_path.read_text(encoding="utf-8")
        html_bytes = html_body.encode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        result.structural_errors.append(f"HTML unreadable: {exc}")
        result.overall_verdict = "FAIL_STRUCTURAL"
        return result

    # NOTE: compiler writes via .write_text(html_body, encoding="utf-8") so
    # the hash MUST be computed over the UTF-8 encoded bytes the compiler
    # produced. Reading as binary is functionally equivalent.
    computed = hashlib.sha256(html_bytes).hexdigest()
    claimed = manifest["output_hash_hex"]
    result.output_hash_claimed = claimed
    result.output_hash_computed = computed
    result.output_hash_match = (computed == claimed)

    if not result.output_hash_match:
        result.overall_verdict = "FAIL_OUTPUT_HASH_MISMATCH"
        return result

    if form == "vpm":
        violations = _run_visual_grammar(html_body)
        result.visual_grammar_violations = violations
        result.visual_grammar_ok = (len(violations) == 0)
        if not result.visual_grammar_ok:
            result.overall_verdict = "FAIL_VISUAL_GRAMMAR"
            return result

    result.overall_verdict = "PASS"
    return result


def _find_manifests(root: Path) -> list[Path]:
    """Recursively find every *.manifest.json under root."""
    return sorted(root.rglob("*.manifest.json"))


def _aggregate_exit_code(results: list[CheckResult]) -> int:
    """Compute the overall exit code from per-artifact verdicts."""
    if not results:
        return 4
    has_hash = any(r.overall_verdict == "FAIL_OUTPUT_HASH_MISMATCH" for r in results)
    has_struct = any(r.overall_verdict == "FAIL_STRUCTURAL" for r in results)
    has_grammar = any(r.overall_verdict == "FAIL_VISUAL_GRAMMAR" for r in results)
    if has_hash:
        return 1
    if has_struct:
        return 2
    if has_grammar:
        return 3
    return 0


def render_human(results: list[CheckResult]) -> str:
    """Human-readable report."""
    lines = []
    lines.append("=" * 70)
    lines.append("VAPI Reproducibility Receipt — external artifact verifier")
    lines.append("=" * 70)
    lines.append(f"Manifests checked: {len(results)}")
    lines.append("")

    pass_count = sum(1 for r in results if r.overall_verdict == "PASS")
    fail_count = len(results) - pass_count
    lines.append(f"PASS: {pass_count}   FAIL: {fail_count}")
    lines.append("")

    for r in results:
        lines.append("-" * 70)
        lines.append(f"manifest: {r.manifest_path}")
        lines.append(f"  schema_form:       {r.schema_form or '<unrecognized>'}")
        lines.append(f"  structural_ok:     {r.structural_ok}")
        if r.structural_errors:
            for e in r.structural_errors:
                lines.append(f"    - {e}")
        lines.append(f"  html_present:      {r.html_present}")
        if r.html_present:
            lines.append(f"  html_path:         {r.html_path_resolved}")
            lines.append(f"  hash_claimed:      {r.output_hash_claimed}")
            lines.append(f"  hash_computed:     {r.output_hash_computed}")
            lines.append(f"  hash_match:        {r.output_hash_match}")
        if r.schema_form == "vpm":
            lines.append(f"  visual_grammar_ok: {r.visual_grammar_ok}")
            if r.visual_grammar_violations:
                for v in r.visual_grammar_violations:
                    lines.append(f"    - {v}")
        lines.append(f"  verdict:           {r.overall_verdict}")

    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="VAPI Reproducibility Receipt — external artifact verifier",
    )
    parser.add_argument(
        "manifest", nargs="?", type=Path,
        help="Path to a single .manifest.json to verify (or omit + use --dir)",
    )
    parser.add_argument(
        "--dir", type=Path,
        help="Recursively verify every *.manifest.json under this directory",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of human report",
    )
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    targets: list[Path] = []
    if args.dir is not None:
        if not args.dir.exists():
            print(f"ERROR: --dir does not exist: {args.dir}", file=sys.stderr)
            return 4
        targets = _find_manifests(args.dir)
        if not targets:
            print(f"ERROR: no *.manifest.json under {args.dir}", file=sys.stderr)
            return 4
    elif args.manifest is not None:
        if not args.manifest.exists():
            print(f"ERROR: manifest does not exist: {args.manifest}", file=sys.stderr)
            return 4
        targets = [args.manifest]
    else:
        parser.print_usage(sys.stderr)
        print("ERROR: pass either a manifest path or --dir", file=sys.stderr)
        return 4

    results = [verify_manifest(p) for p in targets]
    exit_code = _aggregate_exit_code(results)

    if args.json:
        # Convert dataclasses to plain dicts for JSON serialization.
        payload = [
            {
                "manifest_path": r.manifest_path,
                "schema_form": r.schema_form,
                "structural_ok": r.structural_ok,
                "structural_errors": list(r.structural_errors),
                "html_path_resolved": r.html_path_resolved,
                "html_present": r.html_present,
                "output_hash_claimed": r.output_hash_claimed,
                "output_hash_computed": r.output_hash_computed,
                "output_hash_match": r.output_hash_match,
                "visual_grammar_ok": r.visual_grammar_ok,
                "visual_grammar_violations": list(r.visual_grammar_violations),
                "overall_verdict": r.overall_verdict,
            }
            for r in results
        ]
        print(json.dumps({
            "results": payload,
            "exit_code": exit_code,
        }, indent=2, sort_keys=True))
    else:
        print(render_human(results))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
