"""Phase O1 C1 + C7 — Cedar bundle V&V CLI.

Multi-mode tool for validating, diffing, simulating, and linting Cedar
bundles without firing chain transactions. Phase O2 SUGGEST prep — bundle
authors run this BEFORE anchoring to catch issues that would otherwise
require a re-anchor cycle.

Usage:
    python scripts/cedar_bundle_validate.py validate <bundle>
    python scripts/cedar_bundle_validate.py diff <bundle_a> <bundle_b>
    python scripts/cedar_bundle_validate.py simulate <bundle> [--db <path>] [--limit N]
    python scripts/cedar_bundle_validate.py lint <bundle>

Backwards compat: invoking with a single positional path (no subcommand)
runs `validate` mode (Phase O1 C1 behavior preserved).

Exit codes:
    0 — success / clean
    1 — failure / errors found
    2 — usage error
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from bridge.vapi_bridge.cedar_parser import (
    CedarBundleError,
    bundle_merkle_root,
    evaluate,
    parse_bundle,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve(p: str) -> Path:
    bundle_path = Path(p)
    if not bundle_path.is_absolute():
        bundle_path = _PROJECT_ROOT / bundle_path
    return bundle_path


def _load_bundle(p: str):
    """Load + parse + return (raw_payload, parsed). Raises on any error."""
    path = _resolve(p)
    if not path.exists():
        raise FileNotFoundError(f"bundle not found at {path}")
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    parsed = parse_bundle(payload)
    return payload, parsed


# ---------------------------------------------------------------------------
# Mode: validate (Phase O1 C1 behavior, preserved)
# ---------------------------------------------------------------------------

def cmd_validate(args) -> int:
    try:
        payload, parsed = _load_bundle(args.bundle)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
        return 1
    except CedarBundleError as e:
        print(f"ERROR: schema validation failed: {e}", file=sys.stderr)
        return 1

    recompute = bundle_merkle_root(payload)
    if parsed.merkle_root != recompute:
        print(
            f"ERROR: Merkle root round-trip mismatch "
            f"(parser={parsed.merkle_root.hex()} recompute={recompute.hex()})",
            file=sys.stderr,
        )
        return 1

    n_permits = sum(1 for p in parsed.policies if p.effect == "permit")
    n_forbids = sum(1 for p in parsed.policies if p.effect == "forbid")
    print(f"VALID: {Path(args.bundle).name}")
    print(f"  agent_id:      {parsed.agent_id}")
    print(f"  phase:         {parsed.phase}")
    print(f"  version:       {parsed.version}")
    print(f"  issued_at:     {parsed.issued_at_iso}")
    print(f"  lane_prefixes: {list(parsed.lane_prefixes)}")
    print(f"  policies:      {len(parsed.policies)} ({n_permits} permit + {n_forbids} forbid)")
    print(f"  Merkle root:   0x{parsed.merkle_root.hex()}")
    return 0


# ---------------------------------------------------------------------------
# Mode: diff — compare two bundles
# ---------------------------------------------------------------------------

def cmd_diff(args) -> int:
    try:
        _, a = _load_bundle(args.bundle_a)
        _, b = _load_bundle(args.bundle_b)
    except (FileNotFoundError, json.JSONDecodeError, CedarBundleError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"DIFF: {Path(args.bundle_a).name}  <->  {Path(args.bundle_b).name}")
    print()

    # Top-level scalars
    print("HEADER:")
    for field in ("agent_id", "phase", "version", "issued_at_iso"):
        va, vb = getattr(a, field), getattr(b, field)
        marker = " " if va == vb else "*"
        print(f"  {marker} {field:14s}  A={va}  B={vb}")
    print()

    # Lane prefixes
    set_a, set_b = set(a.lane_prefixes), set(b.lane_prefixes)
    only_a = sorted(set_a - set_b)
    only_b = sorted(set_b - set_a)
    print(f"LANES: |A|={len(set_a)}  |B|={len(set_b)}  shared={len(set_a & set_b)}")
    for v in only_a: print(f"  - {v}    (only in A)")
    for v in only_b: print(f"  + {v}    (only in B)")
    print()

    # Policies — compare by id
    a_by_id = {p.id: p for p in a.policies}
    b_by_id = {p.id: p for p in b.policies}
    only_a_ids = sorted(set(a_by_id) - set(b_by_id))
    only_b_ids = sorted(set(b_by_id) - set(a_by_id))
    common_ids = sorted(set(a_by_id) & set(b_by_id))
    changed_ids = []
    for pid in common_ids:
        pa, pb = a_by_id[pid], b_by_id[pid]
        if (pa.effect, pa.action, pa.resource, pa.constraint) != (pb.effect, pb.action, pb.resource, pb.constraint):
            changed_ids.append(pid)

    print(f"POLICIES: |A|={len(a.policies)}  |B|={len(b.policies)}  "
          f"same={len(common_ids) - len(changed_ids)}  changed={len(changed_ids)}")
    for pid in only_a_ids:
        pa = a_by_id[pid]
        print(f"  - {pid}  ({pa.effect} {pa.action} {pa.resource})    (only in A)")
    for pid in only_b_ids:
        pb = b_by_id[pid]
        print(f"  + {pid}  ({pb.effect} {pb.action} {pb.resource})    (only in B)")
    for pid in changed_ids:
        pa, pb = a_by_id[pid], b_by_id[pid]
        print(f"  * {pid}")
        if pa.effect   != pb.effect:   print(f"      effect:    {pa.effect} -> {pb.effect}")
        if pa.action   != pb.action:   print(f"      action:    {pa.action} -> {pb.action}")
        if pa.resource != pb.resource: print(f"      resource:  {pa.resource} -> {pb.resource}")
        if pa.constraint != pb.constraint:
            print(f"      constraint: {pa.constraint} -> {pb.constraint}")
    print()

    # Merkle root
    same_root = a.merkle_root == b.merkle_root
    print(f"MERKLE ROOTS:")
    print(f"  A  0x{a.merkle_root.hex()}")
    print(f"  B  0x{b.merkle_root.hex()}")
    print(f"  {'IDENTICAL' if same_root else 'DIFFERENT'}")

    return 0


# ---------------------------------------------------------------------------
# Mode: simulate — replay shadow log against candidate bundle
# ---------------------------------------------------------------------------

def cmd_simulate(args) -> int:
    try:
        _, candidate = _load_bundle(args.bundle)
    except (FileNotFoundError, json.JSONDecodeError, CedarBundleError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    db_path = args.db
    if not db_path:
        import os
        db_path = os.environ.get("VAPI_DB_PATH", "C:/Users/Contr/.vapi/bridge.db")

    db = Path(db_path)
    if not db.exists():
        print(f"ERROR: bridge DB not found at {db}", file=sys.stderr)
        print(f"       Set VAPI_DB_PATH or pass --db <path>", file=sys.stderr)
        return 1

    import sqlite3
    conn = sqlite3.connect(str(db), timeout=2.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check the table exists (zero shadow data is also a valid simulation result)
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='operator_agent_shadow_log'"
    )
    if not cur.fetchone():
        print("WARNING: operator_agent_shadow_log table does not exist in this DB.")
        print("         No historical evaluations to replay. Bridge may not have been run yet.")
        conn.close()
        return 0

    cur.execute(
        "SELECT agent_id, action, resource, decision, evaluated_at, context_json "
        "FROM operator_agent_shadow_log "
        "WHERE agent_id = ? "
        "ORDER BY evaluated_at DESC LIMIT ?",
        (candidate.agent_id.lower(), int(args.limit)),
    )
    rows = list(cur.fetchall())
    conn.close()

    if not rows:
        print(f"NO HISTORICAL EVALUATIONS for agent_id={candidate.agent_id} in {db}.")
        print(f"  Cannot simulate behavior change without a baseline.")
        return 0

    print(f"SIMULATE: {Path(args.bundle).name}")
    print(f"  agent_id:     {candidate.agent_id}")
    print(f"  source DB:    {db}")
    print(f"  replay count: {len(rows)} historical evaluations")
    print()

    agree = 0
    disagree = 0
    by_change = Counter()  # (original_decision, predicted_decision)
    pred_dist = Counter()

    for r in rows:
        orig = r["decision"]
        # Parse context_json safely — fall back to empty context on JSON error
        try:
            ctx = json.loads(r["context_json"] or "{}")
            if not isinstance(ctx, dict):
                ctx = {}
        except (json.JSONDecodeError, TypeError):
            ctx = {}
        pred = evaluate(
            candidate,
            agent_id=candidate.agent_id,
            action=r["action"] or "",
            resource=r["resource"] or "",
            context=ctx,
        )
        pred_str = pred.value if hasattr(pred, "value") else str(pred)
        pred_dist[pred_str] += 1
        if pred_str == orig:
            agree += 1
        else:
            disagree += 1
            by_change[(orig, pred_str)] += 1

    print("PREDICTED DECISION DISTRIBUTION (under candidate bundle):")
    for dec, count in pred_dist.most_common():
        pct = (count / len(rows)) * 100
        print(f"  {count:5d}  ({pct:5.1f}%)  {dec}")
    print()
    print(f"AGREE WITH ORIGINAL:    {agree:5d} ({(agree / len(rows)) * 100:.1f}%)")
    print(f"DISAGREE (would change): {disagree:5d} ({(disagree / len(rows)) * 100:.1f}%)")
    if disagree > 0:
        print()
        print("MOST COMMON CHANGES (original -> predicted):")
        for (orig, pred), n in by_change.most_common(10):
            print(f"  {n:5d}  {orig}  ->  {pred}")

    return 0


# ---------------------------------------------------------------------------
# Mode: lint — style + safety warnings
# ---------------------------------------------------------------------------

# Resource patterns that are too broad to allow without explicit constraint.
_DANGEROUS_RESOURCES = {"*", "**", "/*", "lane://*", "lane://**"}

# Actions that should always have a shadow_mode constraint in O1_SHADOW phase.
_ACTIONS_REQUIRING_SHADOW = {"tool:kms-sign", "tool:pda-attestation-anchor"}


def cmd_lint(args) -> int:
    try:
        _, parsed = _load_bundle(args.bundle)
    except (FileNotFoundError, json.JSONDecodeError, CedarBundleError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    findings: list[tuple[str, str]] = []  # (severity, message)

    for i, pol in enumerate(parsed.policies):
        # Overly-broad resource on permit policies
        if pol.effect == "permit" and pol.resource in _DANGEROUS_RESOURCES:
            findings.append((
                "HIGH",
                f"policies[{i}] id={pol.id!r}: permit on overly-broad resource {pol.resource!r}",
            ))

        # Phase-specific: O1_SHADOW must constrain dangerous actions
        if (
            parsed.phase == "O1_SHADOW"
            and pol.effect == "permit"
            and pol.action in _ACTIONS_REQUIRING_SHADOW
            and not (pol.constraint and pol.constraint.get("shadow_mode") is True)
        ):
            findings.append((
                "CRITICAL",
                f"policies[{i}] id={pol.id!r}: O1_SHADOW phase + permit action {pol.action!r} "
                f"WITHOUT shadow_mode:true constraint — would allow real-world side effects",
            ))

        # Permit on lane:// resource not covered by any lane_prefix.
        # Mirrors cedar_parser._lane_violation: strip "lane://" scheme, then
        # check against bundle.lane_prefixes (which are stored as path-only,
        # e.g., "events/", not "lane://events/").
        if pol.effect == "permit" and pol.resource.startswith("lane://"):
            after_scheme = pol.resource[len("lane://"):]
            matched = any(after_scheme.startswith(lp) for lp in parsed.lane_prefixes)
            if not matched:
                findings.append((
                    "HIGH",
                    f"policies[{i}] id={pol.id!r}: permit on lane:// resource {pol.resource!r} "
                    f"NOT covered by any lane_prefix — will be denied at evaluate via "
                    f"FORBID_LANE_VIOLATION",
                ))

    # Bundle-level: empty lane_prefixes is suspicious for any non-trivial bundle
    if not parsed.lane_prefixes and any(p.effect == "permit" for p in parsed.policies):
        findings.append((
            "MEDIUM",
            "bundle has 0 lane_prefixes but >=1 permit policy — agent cannot act in any lane",
        ))

    print(f"LINT: {Path(args.bundle).name}")
    print(f"  agent_id:    {parsed.agent_id}")
    print(f"  phase:       {parsed.phase}")
    print(f"  policies:    {len(parsed.policies)}")
    print()
    if not findings:
        print("  no findings (clean)")
        return 0
    for sev, msg in findings:
        print(f"  [{sev}] {msg}")
    has_critical = any(s == "CRITICAL" for s, _ in findings)
    return 1 if has_critical else 0


# ---------------------------------------------------------------------------
# Argparse + backwards compat
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cedar_bundle_validate",
        description="Cedar bundle V&V CLI — validate, diff, simulate, lint",
    )
    sub = parser.add_subparsers(dest="cmd")

    p_validate = sub.add_parser("validate", help="schema + Merkle round-trip check")
    p_validate.add_argument("bundle")
    p_validate.set_defaults(func=cmd_validate)

    p_diff = sub.add_parser("diff", help="compare two bundles")
    p_diff.add_argument("bundle_a")
    p_diff.add_argument("bundle_b")
    p_diff.set_defaults(func=cmd_diff)

    p_sim = sub.add_parser("simulate",
                           help="replay shadow log evaluations against candidate bundle")
    p_sim.add_argument("bundle")
    p_sim.add_argument("--db", default=None,
                       help="path to bridge DB (default: VAPI_DB_PATH or operator's standard)")
    p_sim.add_argument("--limit", type=int, default=500,
                       help="max shadow log rows to replay (default 500)")
    p_sim.set_defaults(func=cmd_simulate)

    p_lint = sub.add_parser("lint", help="policy safety + style warnings")
    p_lint.add_argument("bundle")
    p_lint.set_defaults(func=cmd_lint)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])

    # Backwards compat: single positional path with no subcommand -> validate.
    # Phase O1 C1 invocation pattern:
    #   python scripts/cedar_bundle_validate.py <bundle.json>
    if (
        len(argv) == 1
        and not argv[0].startswith("-")
        and argv[0] not in {"validate", "diff", "simulate", "lint"}
    ):
        argv = ["validate", argv[0]]

    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
