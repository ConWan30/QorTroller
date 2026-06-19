"""Build an extraction-ONLY _core.py from the HEAD baseline (no ioID WIP).

Stages cleanly: working tree keeps (HEAD + ioID + extraction); this produces
(HEAD + extraction) so the committed blob excludes the unrelated controller-ioID
WIP. Verifies the only delta between blob and working tree is the ioID hunks.
"""
from __future__ import annotations

import difflib
import importlib.util
import subprocess
import sys

spec = importlib.util.spec_from_file_location("_ext", "scripts/_extract_tournament_mixin.py")
ext = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ext)

CORE_REL = "bridge/vapi_bridge/store/_core.py"
OUT = "scripts/_core_extraction_only.tmp"

head = subprocess.run(
    ["git", "show", f"HEAD:{CORE_REL}"],
    capture_output=True, text=True, encoding="utf-8",
)
if head.returncode != 0:
    print("git show failed:", head.stderr)
    sys.exit(2)
head_src = head.stdout

lines, spans, nodes = ext._method_spans(head_src)
missing = [t for t in ext.TARGETS if t not in spans]
assert not missing, f"missing in HEAD: {missing}"

ordered = sorted(spans.items(), key=lambda kv: kv[1][0])
delete = set()
for name, (s, e) in ordered:
    for ln in range(s, e + 1):
        delete.add(ln)
    if e < len(lines) and lines[e].strip() == "":
        delete.add(e + 1)
new_lines = [ln for i, ln in enumerate(lines, start=1) if i not in delete]
core = "".join(new_lines)

imp_old = "from .chain_log import ChainLogMixin\n"
imp_new = "from .chain_log import ChainLogMixin\nfrom .tournament import TournamentMixin\n"
assert core.count(imp_old) >= 1, "import anchor not found"
core = core.replace(imp_old, imp_new, 1)

base_old = "class Store(ZkbaVpmMixin, MarketplaceMixin, ConsentMixin, SnapshotsGrindMixin, IoswarmMixin, ChainLogMixin):"
base_new = "class Store(ZkbaVpmMixin, MarketplaceMixin, ConsentMixin, SnapshotsGrindMixin, IoswarmMixin, ChainLogMixin, TournamentMixin):"
assert core.count(base_old) == 1, "base-class anchor not found/unique"
core = core.replace(base_old, base_new, 1)

open(OUT, "w", encoding="utf-8", newline="\n").write(core)
print(f"WROTE {OUT} ({core.count(chr(10))} lines)")

# verify: working tree == blob + ioID hunks (diff should be ADD-only = ioID)
work = open(CORE_REL, encoding="utf-8").read()
diff = list(difflib.unified_diff(core.splitlines(), work.splitlines(), lineterm="", n=0))
added = [d for d in diff if d.startswith("+") and not d.startswith("+++")]
removed = [d for d in diff if d.startswith("-") and not d.startswith("---")]
print(f"\nblob-vs-working: {len(added)} added (ioID WIP present in working) / {len(removed)} removed")
print("--- added lines (must all be ioID/controller-identity WIP) ---")
for d in added:
    print("  ", d)
if removed:
    print("!!! UNEXPECTED removed lines (working diverges from blob beyond ioID):")
    for d in removed:
        print("  ", d)
    sys.exit(3)
