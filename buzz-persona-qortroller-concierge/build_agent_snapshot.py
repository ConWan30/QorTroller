#!/usr/bin/env python3
"""Build qortroller-concierge.agent.json from the persona pack files.

Usage:
    python build_agent_snapshot.py
    python build_agent_snapshot.py --out C:\path\to\qortroller-concierge.agent.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from a .persona.md or .md file."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def _read_markdown(path: Path) -> str:
    return _strip_frontmatter(path.read_text(encoding="utf-8"))


def build_snapshot() -> dict:
    persona = _read_markdown(PACK_DIR / "agents" / "qortroller-concierge.persona.md")
    instructions = _read_markdown(PACK_DIR / "instructions.md")
    skill = _read_markdown(PACK_DIR / "skills" / "qortroller-concierge" / "SKILL.md")

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
            "name": "qortroller-concierge",
            "sourceIsBuiltin": False,
            "systemPrompt": system_prompt,
            "runtime": "grok-build",
            "model": "grok-4.5",
            "provider": "xai",
            "parallelism": 1,
            "respondTo": "anyone",
            "respondToAllowlist": [],
            "namePool": [],
            "idleTimeoutSeconds": 300,
            "maxTurnDurationSeconds": 600,
        },
        "profile": {
            "displayName": "QorTroller Concierge",
            "about": "Gamer-facing self-service and agentic creation for QorTroller (Grok 4.5, Goose harness, grok-build ACP relay).",
            "avatarDataUrl": None,
            "avatarUrl": None,
        },
        "memory": {
            "level": "none",
            "entries": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(PACK_DIR / "qortroller-concierge.agent.json"),
        help="Output .agent.json path",
    )
    args = parser.parse_args()

    snapshot = build_snapshot()
    out = Path(args.out)
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
