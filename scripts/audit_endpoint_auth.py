#!/usr/bin/env python3
"""
Audit all /agent/* endpoints in operator_api.py for missing auth checks.

HISTORY OF BUG — what the original ad-hoc analysis did wrong:
--------------------------------------------------------------
The original session-time detection script scanned the source file by splitting
on '@app.' decorator markers and then inspecting only the first 800 characters
of each block:

    for block in re.split(r'(?=@app[.])', source):
        if '/agent/' not in block[:200]:
            continue
        has_auth = ('_check_key' in block[:800] or '_check_read_key' in block[:800])
        if not has_auth:
            unauthenticated.append(...)

Two bugs:
  1. [:800] character window — Phase 221-225 endpoints have multi-line docstrings
     (~400-600 chars) that push _check_read_key() past the 800-char boundary,
     producing false "no auth" classifications.

  2. ^@app[.] anchor — all routes are defined inside create_operator_app() so every
     decorator is indented by 4 spaces. A column-0 anchor never matches, meaning the
     split never fires and the entire file becomes one block.

This script corrects both bugs:
  - Split anchor: ^ {4}@app[.] (matches the 4-space indent)
  - No character window: searches the entire block for auth calls
"""

import re
import sys
from pathlib import Path

# --- configuration -----------------------------------------------------------
TARGET = Path(__file__).parent.parent / "bridge" / "vapi_bridge" / "operator_api.py"

# Match a route decorator at exactly 4-space indent (all routes are inside create_operator_app)
_DECORATOR_RE = re.compile(r"^    @app\.(get|post|put|delete|patch)\b", re.MULTILINE)

# Extract the URL path from the decorator
_PATH_RE = re.compile(r"""@app\.\w+\(\s*["']([^"']+)["']""")

# Auth call patterns
_AUTH_CALLS = ("_check_key(", "_check_read_key(")


def audit(source: str) -> dict:
    """
    Split source on '    @app.' decorator lines (4-space indent, anchored).
    Search the ENTIRE block — no character-window limit.
    """
    # Split while keeping the delimiter via zero-width lookahead
    blocks = re.split(r"(?m)(?=^    @app\.)", source)

    results = {
        "total_agent_routes": 0,
        "authenticated": [],
        "unauthenticated": [],
        "skipped_non_agent": 0,
    }

    for block in blocks:
        if not _DECORATOR_RE.match(block):
            results["skipped_non_agent"] += 1
            continue

        path_m = _PATH_RE.search(block)
        if not path_m:
            continue
        path = path_m.group(1)

        if "/agent/" not in path:
            results["skipped_non_agent"] += 1
            continue

        results["total_agent_routes"] += 1

        # Check ENTIRE block — no [:800] window
        has_auth = any(call in block for call in _AUTH_CALLS)

        # Extract handler name
        fn_m = re.search(r"^    (?:async )?def (\w+)", block, re.MULTILINE)
        fn_name = fn_m.group(1) if fn_m else "<unknown>"

        # HTTP method
        method_m = re.match(r"    @app\.(\w+)", block)
        method = method_m.group(1).upper() if method_m else "?"

        # Auth style
        if "_check_read_key(" in block:
            auth_style = "_check_read_key (Phase 221+ header)"
        elif "_check_key(" in block:
            auth_style = "_check_key (query-param)"
        else:
            auth_style = "NONE"

        entry = {
            "method": method,
            "path": path,
            "handler": fn_name,
            "auth": auth_style,
        }

        if has_auth:
            results["authenticated"].append(entry)
        else:
            results["unauthenticated"].append(entry)

    return results


def main() -> int:
    source = TARGET.read_text(encoding="utf-8")
    r = audit(source)

    n_query  = sum(1 for e in r["authenticated"] if "query-param" in e["auth"])
    n_header = sum(1 for e in r["authenticated"] if "Phase 221" in e["auth"])

    print(f"Scanned:  {TARGET}")
    print(f"Total /agent/* routes:   {r['total_agent_routes']}")
    print(f"  authenticated:         {len(r['authenticated'])}")
    print(f"    _check_key  (query): {n_query}")
    print(f"    _check_read_key (h): {n_header}")
    print(f"  UNAUTHENTICATED:       {len(r['unauthenticated'])}")
    print()

    if r["unauthenticated"]:
        print("FAIL — unauthenticated /agent/* endpoints found:")
        for e in r["unauthenticated"]:
            print(f"  [{e['method']:6s}] {e['path']}  (handler: {e['handler']})")
        return 1

    print("PASS — all /agent/* endpoints are authenticated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
