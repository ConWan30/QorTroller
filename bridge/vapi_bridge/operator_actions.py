"""Shared OPERATOR-ACTION box renderer (HWFL-1, 2026-07-17).

Single source of truth for the standing OPERATOR-ACTION box that BOTH Sensor C
(rung-gate ledger) and Sensor B (supply/standards watch) render into their
per-cycle artifacts. Replaces the byte-identical dual hardcode that went stale
after the F-DECON-3.2 root fix — the same dual-site drift disease HWFL-1 Cycle 9
caught in the sanitization pass. One data file, one renderer, two consumers.

Discipline (LOAD-BEARING):
  - Statuses are OPERATOR ATTESTATIONS. This module RENDERS them; it NEVER
    writes, infers, or mutates a status. "loop never auto-touches" becomes
    "loop never auto-attests". An item flips open→done only when the operator
    edits `audits/operator_actions.json`. There is deliberately NO write path
    in this module (Cycle-8 `[when true]` discipline preserved).
  - `machine_hint` is ADVISORY ONLY — a rendered pointer, never a second
    status. A hint can never flip a checkbox.
  - Sanitization rail (F-CYCLE8-1 / F-CYCLE9-1): neither the data file nor this
    renderer may reproduce the CA filename, raw AWS ARNs, or `~/.vapi` absolute
    paths in a public artifact. The private-runbook PATH NAME
    (`docs/disaster-recovery-runbook.private.md`) is already public and allowed.
    Any item whose rendered text contains a forbidden token is REDACTED whole —
    the token never reaches the output — as active defense, not just a test.
  - Fallback: file missing / malformed / wrong-schema → an honest MISSING
    banner, NEVER the stale legacy hardcoded box (shipping v1 forever would
    freeze the very lies this refactor removes). This repo ships
    `audits/operator_actions.json` as the canonical source.
"""
from __future__ import annotations

import json
from pathlib import Path

_SCHEMA = "vapi-operator-actions-v1"
_REL_PATH = ("audits", "operator_actions.json")

# open renders "[ ]"; every other status renders "[x]" + an explicit tag.
_VALID_STATUSES = {"open", "done", "superseded", "moot", "partial"}

# Sanitization rail — lower-cased substring match. `qortroller_foundation_mfg_ca`
# also covers the `.json` suffix. The private-runbook path name is NOT here (it
# is already public).
_FORBIDDEN_TOKENS = ("qortroller_foundation_mfg_ca", "arn:aws:", "~/.vapi")

_HEADER = "## Standing OPERATOR-ACTION box (loop renders; operator attests)"

_MISSING_BANNER = (
    "_Source `audits/operator_actions.json` missing, malformed, or wrong-schema "
    "— no attested actions rendered. This repo ships the file; a clone without "
    "it (or a bad edit) shows this banner rather than stale hardcoded text._"
)


def _resolve_repo_root(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return Path(repo_root)
    # This module lives at bridge/vapi_bridge/operator_actions.py → repo root is
    # two parents up. Lets both sensors call render_operator_actions() with no
    # plumbing while still allowing an explicit override for hermetic tests.
    return Path(__file__).resolve().parents[2]


def _forbidden_token(text: str) -> str | None:
    low = text.lower()
    for tok in _FORBIDDEN_TOKENS:
        if tok in low:
            return tok
    return None


def _render_item(item: dict) -> str:
    oa_id = str(item.get("id", "OA-?")).strip() or "OA-?"
    status = str(item.get("status", "open")).strip().lower()
    if status not in _VALID_STATUSES:
        # Fail-open: an unknown status renders as OPEN (unchecked). NEVER silently
        # promote to done/[x] — that would be the loop attesting on its own.
        status = "open"
    text = str(item.get("text", "")).strip()
    note = str(item.get("attested_note", "")).strip()
    date = str(item.get("attested_date", "")).strip()
    hint = item.get("machine_hint") if isinstance(item.get("machine_hint"), dict) else {}
    hint_kind = str(hint.get("kind", "none")).strip().lower()
    hint_ref = str(hint.get("ref", "")).strip()

    # Sanitization: refuse to emit ANY forbidden token; redact the whole item.
    # Scan the FULL hint dict (not just hint_ref) for defense-in-depth — a
    # forbidden token in any hint key can never reach a future render (round-31 F2).
    scan = " ".join([oa_id, text, note, json.dumps(hint, sort_keys=True, ensure_ascii=True)])
    if _forbidden_token(scan) is not None:
        return (f"- [ ] **{oa_id}** _[REDACTED — a sanitization-forbidden token is "
                f"present in audits/operator_actions.json; fix the source]_")

    checkbox = "[ ]" if status == "open" else "[x]"
    line = f"- {checkbox} **{oa_id}** ({status})"
    if text:
        line += f" {text}"

    tail: list[str] = []
    if date or note:
        meta = f"attested {date}" if date else "attested"
        if note:
            meta += f": {note}"
        tail.append(f"_{meta}_")
    if hint_kind == "path_exists" and hint_ref:
        tail.append(f"(hint: path `{hint_ref}`)")
    elif hint_kind == "doc_pointer" and hint_ref:
        tail.append(f"(hint: see `{hint_ref}`)")
    if tail:
        line += " — " + " ".join(tail)
    return line


def render_operator_actions(repo_root: Path | None = None) -> str:
    """Render the standing OPERATOR-ACTION box as a self-contained markdown block.

    Reads the operator-attested `audits/operator_actions.json`. Statuses are
    operator attestations — this function renders them and NEVER writes or infers
    one. Fail-open: any missing/malformed/wrong-schema/exception condition returns
    the honest MISSING banner (never the stale legacy hardcoded box, never a
    crash — a sensor render must survive a bad OA file).
    """
    path = _resolve_repo_root(repo_root).joinpath(*_REL_PATH)
    try:
        if not path.exists():
            return f"\n{_HEADER}\n\n{_MISSING_BANNER}\n"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != _SCHEMA:
            return f"\n{_HEADER}\n\n{_MISSING_BANNER}\n"
        items = data.get("items")
        if not isinstance(items, list) or not items:
            return f"\n{_HEADER}\n\n{_MISSING_BANNER}\n"

        out = [f"\n{_HEADER}\n"]
        note = str(data.get("note", "")).strip()
        if note and _forbidden_token(note) is None:
            out.append(f"_{note}_\n")
        for item in items:
            if isinstance(item, dict):
                out.append(_render_item(item))
        out.append("")
        return "\n".join(out)
    except Exception:  # noqa: BLE001 — fail-open: a sensor render must never crash
        return f"\n{_HEADER}\n\n{_MISSING_BANNER}\n"
