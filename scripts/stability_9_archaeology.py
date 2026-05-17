"""Phase 235.x-STABILITY-9 archaeological sweep (2026-05-17).

Per operator /goal directive: surface vulnerabilities/bugs/problems/
causes from VAPI Protocol genesis to current state, until a
solution/fix could be made.

The 9 existing Mythos variants all return 0 findings — they encode
STATIC patterns (frozen-constant drift, crypto-tag drift, etc.)
that are clean. The residual 50-70s loop_starvation events surface
through BEHAVIORAL antipatterns: async functions that secretly
block, hot paths that synchronously hit SQLite, subprocess calls
on the event loop thread.

This sweep targets the 8 specific antipatterns historically
implicated in VAPI's stability arc (STABILITY → STABILITY-8):

  AP1. async def body containing NO await expression at all
       (the FSCA *_sync chain antipattern that STABILITY-2 fixed)
  AP2. time.sleep(...) inside an async def (blocks event loop)
  AP3. requests.{get,post,put,delete}(...) inside an async def
       (blocking HTTP — should be httpx/aiohttp)
  AP4. subprocess.run(...) inside an async def (blocking exec —
       should be asyncio.create_subprocess_exec)
  AP5. subprocess.Popen(...).communicate() inside async def
  AP6. open(path).read() / write() inside an async def hot path
       (blocking file I/O — micro but adds up)
  AP7. Store.<method> SQLite calls inside async def WITHOUT
       being wrapped in asyncio.to_thread (the STABILITY-4/5/8
       offender pattern)
  AP8. Bare `while True:` loop without await asyncio.sleep at
       a yield point inside the body (busy-spin)

Findings are written to stderr as JSON-line records. Operator can
pipe to a file or jq for triage.

Read-only; no DB writes; no chain ops; safe to run anywhere.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable, List, Dict, Any


REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIRS = [REPO_ROOT / "bridge" / "vapi_bridge"]
EXCLUDE_SUBSTRS = ("/tests/", "\\tests\\", "/__pycache__/", "\\__pycache__\\")


_PAT_ASYNC_DEF = re.compile(r"^(?P<indent>\s*)async\s+def\s+(?P<name>\w+)\s*\(", re.MULTILINE)
_PAT_AWAIT = re.compile(r"\bawait\s")
_PAT_TIME_SLEEP = re.compile(r"(?<!asyncio\.)\btime\.sleep\s*\(")
_PAT_REQUESTS = re.compile(r"\brequests\.(get|post|put|delete|patch|head)\s*\(")
_PAT_SUBPROCESS_RUN = re.compile(r"\bsubprocess\.run\s*\(")
_PAT_SUBPROCESS_POPEN = re.compile(r"\bsubprocess\.Popen\s*\([^)]*\)\.communicate\s*\(")
_PAT_OPEN_READ = re.compile(r"\bopen\s*\([^)]+\)\.(read|write)\s*\(")
_PAT_STORE_CALL = re.compile(r"\bself\.(_store|store)\.[a-z_]+\s*\(")
_PAT_TO_THREAD = re.compile(r"\basyncio\.to_thread\s*\(")
_PAT_WHILE_TRUE = re.compile(r"^\s*while\s+True\s*:", re.MULTILINE)
_PAT_AWAIT_SLEEP = re.compile(r"\bawait\s+asyncio\.sleep\s*\(")


def _iter_files() -> Iterable[Path]:
    for d in AUDIT_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            sp = str(p)
            if any(x in sp for x in EXCLUDE_SUBSTRS):
                continue
            yield p


def _extract_async_bodies(text: str) -> List[Dict[str, Any]]:
    """Yield (name, line, body_text) for each async def.

    Body is captured greedily from the def line until the next
    top-or-equal-indent non-blank line (heuristic; good enough for
    catching the antipatterns above)."""
    results = []
    lines = text.splitlines(keepends=True)
    starts = []
    for m in _PAT_ASYNC_DEF.finditer(text):
        starts.append((m.start(), m.group("name"), len(m.group("indent"))))
    for i, (start, name, indent) in enumerate(starts):
        # line number
        line_no = text.count("\n", 0, start) + 1
        # capture until the next async def at <= indent, or EOF
        end = len(text)
        for nstart, nname, nindent in starts[i + 1 :]:
            if nindent <= indent:
                end = nstart
                break
        body = text[start:end]
        results.append({"name": name, "line": line_no, "body": body, "indent": indent})
    return results


def _scan_file(p: Path) -> List[Dict[str, Any]]:
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return []
    rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
    findings: List[Dict[str, Any]] = []
    bodies = _extract_async_bodies(text)
    for b in bodies:
        body = b["body"]
        name = b["name"]
        line = b["line"]
        # AP1: async def with no await
        if not _PAT_AWAIT.search(body):
            findings.append(
                {"ap": "AP1", "file": rel, "line": line, "func": name,
                 "detail": "async def with no await expression — secretly blocking"}
            )
        # AP2: time.sleep in async
        for m in _PAT_TIME_SLEEP.finditer(body):
            offset = m.start()
            line_in_body = body.count("\n", 0, offset)
            findings.append(
                {"ap": "AP2", "file": rel, "line": line + line_in_body, "func": name,
                 "detail": "time.sleep() inside async def — blocks event loop"}
            )
        # AP3: requests.* in async
        for m in _PAT_REQUESTS.finditer(body):
            offset = m.start()
            line_in_body = body.count("\n", 0, offset)
            findings.append(
                {"ap": "AP3", "file": rel, "line": line + line_in_body, "func": name,
                 "detail": f"requests.{m.group(1)}() inside async def — use httpx/aiohttp"}
            )
        # AP4: subprocess.run in async
        for m in _PAT_SUBPROCESS_RUN.finditer(body):
            offset = m.start()
            line_in_body = body.count("\n", 0, offset)
            findings.append(
                {"ap": "AP4", "file": rel, "line": line + line_in_body, "func": name,
                 "detail": "subprocess.run() inside async def — use asyncio.create_subprocess_exec"}
            )
        # AP5: subprocess.Popen().communicate() in async
        for m in _PAT_SUBPROCESS_POPEN.finditer(body):
            offset = m.start()
            line_in_body = body.count("\n", 0, offset)
            findings.append(
                {"ap": "AP5", "file": rel, "line": line + line_in_body, "func": name,
                 "detail": "subprocess.Popen().communicate() inside async def — blocking"}
            )
        # AP6: open().read/write in async
        for m in _PAT_OPEN_READ.finditer(body):
            offset = m.start()
            line_in_body = body.count("\n", 0, offset)
            findings.append(
                {"ap": "AP6", "file": rel, "line": line + line_in_body, "func": name,
                 "detail": f"open(...).{m.group(1)}() inside async def — blocking file I/O"}
            )
        # AP7: Store.X() not wrapped in to_thread — heuristic: store call appears
        # in body but no nearby to_thread call. Refined to reduce noise: only flag
        # when store call is on its own line AND no `to_thread` appears anywhere
        # in the body.
        if not _PAT_TO_THREAD.search(body):
            for m in _PAT_STORE_CALL.finditer(body):
                offset = m.start()
                line_in_body = body.count("\n", 0, offset)
                # skip getattr() probes and dict access patterns
                line_text = body[max(0, offset - 60):offset + 80]
                if "getattr(" in line_text:
                    continue
                findings.append(
                    {"ap": "AP7", "file": rel, "line": line + line_in_body, "func": name,
                     "detail": "Store.<method>() inside async def without asyncio.to_thread wrap"}
                )
        # AP8: while True with no await sleep inside body
        for m in _PAT_WHILE_TRUE.finditer(body):
            offset = m.start()
            # peek at next ~25 lines of body after the while
            tail = body[offset:offset + 1200]
            if not _PAT_AWAIT_SLEEP.search(tail) and not _PAT_AWAIT.search(tail):
                line_in_body = body.count("\n", 0, offset)
                findings.append(
                    {"ap": "AP8", "file": rel, "line": line + line_in_body, "func": name,
                     "detail": "while True loop without yield point — busy spin"}
                )
    return findings


def main() -> int:
    all_findings: List[Dict[str, Any]] = []
    files_scanned = 0
    for p in _iter_files():
        files_scanned += 1
        all_findings.extend(_scan_file(p))
    # roll up
    by_ap: Dict[str, int] = {}
    by_file: Dict[str, int] = {}
    for f in all_findings:
        by_ap[f["ap"]] = by_ap.get(f["ap"], 0) + 1
        by_file[f["file"]] = by_file.get(f["file"], 0) + 1
    summary = {
        "files_scanned": files_scanned,
        "total_findings": len(all_findings),
        "by_antipattern": dict(sorted(by_ap.items())),
        "top_files": dict(sorted(by_file.items(), key=lambda x: -x[1])[:15]),
    }
    print(json.dumps(summary, indent=2))
    # full findings on stderr for triage
    for f in all_findings:
        print(json.dumps(f), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
