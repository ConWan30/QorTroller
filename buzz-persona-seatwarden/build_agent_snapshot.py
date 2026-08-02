#!/usr/bin/env python3
"""Build seatwarden.agent.json from the persona pack files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def _read_markdown(path: Path) -> str:
    return _strip_frontmatter(path.read_text(encoding="utf-8"))


def build_snapshot() -> dict:
    persona = _read_markdown(PACK_DIR / "agents" / "seatwarden.persona.md")
    instructions = _read_markdown(PACK_DIR / "instructions.md")
    skill = _read_markdown(PACK_DIR / "skills" / "seatwarden" / "SKILL.md")
    system_prompt = f"""{persona}

---
# Pack Instructions

{instructions}

---
# Skill Reference

{skill}
"""
    return {
        "format": "buzz-agent-snapshot",
        "version": 1,
        "definition": {
            "name": "seatwarden",
            "sourceIsBuiltin": False,
            "systemPrompt": system_prompt,
            "runtime": "hermes",
            "model": "z-ai/glm-5.2",
            "parallelism": 5,
            "respondTo": "anyone",
            "respondToAllowlist": [],
            "namePool": [],
            "idleTimeoutSeconds": 300,
            "maxTurnDurationSeconds": 600,
        },
        "profile": {
            "displayName": "Seatwarden",
            "about": "P-VSS seat status — eligibility & flag-down only; never OPEN (charter v1).",
            "avatarDataUrl": None,
            "avatarUrl": None,
        },
        "memory": {"level": "none", "entries": []},
        "charter": {
            "clause": "P-VSS",
            "channels": ["#streams"],
            "forbidden": ["VSS OPEN", "keys", "shell", "chain", "claim inflation"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PACK_DIR / "seatwarden.agent.json"))
    parser.add_argument("--prompt-only", action="store_true", help="Print system prompt only")
    args = parser.parse_args()
    snap = build_snapshot()
    if args.prompt_only:
        print(snap["definition"]["systemPrompt"])
        return 0
    Path(args.out).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
