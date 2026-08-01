#!/usr/bin/env python3
"""Machine-readable claim register client for Phase 5 public language.

Usage:
    python scripts/buzz_claim_register.py list
    python scripts/buzz_claim_register.py check "tournament-grade anti-cheat"
    python scripts/buzz_claim_register.py validate docs/publish/my-post.md

The register lives at `docs/design/buzz-phase5-claim-register.json` and is the
machine-readable twin of `docs/design/buzz-phase5-claim-register-v0.md`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTER = REPO_ROOT / "docs" / "design" / "buzz-phase5-claim-register.json"


@dataclass
class RegisterMatch:
    row_id: str
    phrase: str
    grade: str
    gates: list[str]
    sayable_today: bool


def load_register(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"claim register missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _row_matches(text: str, phrase: str) -> bool:
    """Heuristic: does the input text contain the claim phrase or a close variant?"""
    text = text.lower()
    phrase = phrase.lower()
    # Direct containment of the whole phrase.
    if phrase in text:
        return True
    # Distinctive content words (>=4 letters, excluding common connective words).
    stop = {"this", "that", "with", "from", "for", "the", "and", "are", "any", "can", "may", "not"}
    content_words = [w for w in re.findall(r"\b[a-z]{4,}\b", phrase) if w not in stop]
    if not content_words:
        return False
    overlap = [w for w in content_words if w in text]
    # Exact match of all content words.
    if len(overlap) == len(content_words):
        return True
    # Allow one missing word for short phrases; for longer phrases require 3+ matches.
    if len(content_words) <= 4 and len(overlap) >= max(2, len(content_words) - 1):
        return True
    if len(content_words) > 4 and len(overlap) >= 3:
        return True
    return False


def check_phrase(text: str, register_path: Path = DEFAULT_REGISTER) -> dict:
    """Return the most specific matching row, plus any forbidden substrings."""
    register = load_register(register_path)
    matches: list[RegisterMatch] = []
    for row in register["rows"]:
        if _row_matches(text, row["phrase"]):
            matches.append(
                RegisterMatch(
                    row_id=row["id"],
                    phrase=row["phrase"],
                    grade=row["grade"],
                    gates=row.get("gates", []),
                    sayable_today=row.get("sayable_today", False),
                )
            )
    forbidden_hits = [fp for fp in register.get("forbidden_phrases", []) if fp.lower() in text.lower()]
    # Prefer the most specific (highest grade / most gates) match.
    grade_order = {"G4": 4, "G3": 3, "G2": 2, "G1": 1, "G0": 0}
    matches.sort(key=lambda m: (grade_order.get(m.grade, 0), len(m.gates)), reverse=True)
    return {
        "input": text,
        "matches": [m.__dict__ for m in matches],
        "best_match": matches[0].__dict__ if matches else None,
        "forbidden_hits": forbidden_hits,
        "approved": bool(matches and matches[0].sayable_today and not forbidden_hits),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check public language against the Phase 5 claim register.")
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER, help="Path to claim register JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all rows")

    p_check = sub.add_parser("check", help="Check whether a phrase is sayable")
    p_check.add_argument("phrase", help="Phrase to check")

    p_validate = sub.add_parser("validate", help="Validate a markdown file for disallowed claims")
    p_validate.add_argument("file", type=Path, help="Markdown file to validate")

    args = parser.parse_args(argv)

    if args.command == "list":
        register = load_register(args.register)
        for row in register["rows"]:
            print(f"{row['id']:10} {row['grade']:3} sayable={row['sayable_today']!s:5} {row['phrase'][:70]}")
        return 0

    if args.command == "check":
        result = check_phrase(args.phrase, args.register)
        print(json.dumps(result, indent=2, sort_keys=True))
        if result["forbidden_hits"]:
            print("! forbidden phrase(s) detected", file=sys.stderr)
        if result["best_match"]:
            if result["best_match"]["sayable_today"]:
                print(f"OK: matched {result['best_match']['row_id']} ({result['best_match']['grade']}) and is sayable today")
            else:
                print(f"NO: matched {result['best_match']['row_id']} ({result['best_match']['grade']}) but is not sayable today; gates={result['best_match']['gates']}")
        else:
            print("NO: no register row matched (if the sentence makes a product claim, it is not approved language)")
        return 0 if result["approved"] else 1

    if args.command == "validate":
        text = args.file.read_text(encoding="utf-8")
        result = check_phrase(text, args.register)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["approved"] else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
