"""One-off CLAUDE.md curation (2026-05-22) — lossless archive pass.

Continues the discipline established by scripts/_prune_claude_md.py (2026-05-18).
Moves 7 completed-arc NOTEs + the Phase 109A-229 Phase Summary rows verbatim into
wiki/phases/phase_archive_2026_05_notes_and_summary.md, replacing them inline with
compact pointer entries. Operational sections (Hard Rules, Key Gotchas, Architecture,
calibration thresholds, FROZEN formulas, build commands) are left untouched.

Anchor-guarded: aborts without writing if any expected line does not match, so a
line-count drift can never silently delete the wrong content.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / "CLAUDE.md"
WIKI = ROOT / "wiki" / "phases" / "phase_archive_2026_05_notes_and_summary.md"

raw = CLAUDE.read_text(encoding="utf-8")
NL = "\r\n" if "\r\n" in raw else "\n"
lines = raw.splitlines(keepends=True)


def fail(msg: str) -> None:
    print("ABORT (no files written):", msg)
    sys.exit(1)


# ---- anchor verification (0-indexed) -------------------------------------
def has(i: int, needle: str) -> bool:
    return 0 <= i < len(lines) and needle in lines[i]


checks = [
    (31, "GUARDIAN AUTONOMOUS KMS-HSM"),       # keep (HEAD)
    (32, "QRESCE-0001 v0.5 BRAND-LAYER REFRAMING"),  # archive
    (33, "QRESCE-0001 v0.5 BRAND LOCKED"),     # archive
    (34, "PHASE 2 R0 DEEP-VERIFICATION"),      # archive
    (35, "PHASE 1 POST-STABILITY-9 CLEANUP"),  # archive
    (36, "STABILITY-9 EMPIRICAL CLOSURE"),     # archive
    (37, "PHASE O1-D-PATH-B v1 COMPLETE"),     # archive
    (38, "O3 CEREMONY FIRED LIVE"),            # keep
    (39, "PHASE O1-D-AUTO-SUPERSEDE COMPLETE"),# archive
]
for i, needle in checks:
    if not has(i, needle):
        fail(f"NOTE anchor failed at line {i+1}: expected '{needle}'")

if not lines[189].startswith("| 230 "):
    fail(f"table anchor failed: line 190 should be Phase 230 row, got: {lines[189][:40]!r}")
if not lines[190].startswith("| 229 "):
    fail(f"table anchor failed: line 191 should be Phase 229 row, got: {lines[190][:40]!r}")
if not lines[269].startswith("| 109A "):
    fail(f"table anchor failed: line 270 should be Phase 109A row, got: {lines[269][:40]!r}")

# ---- collect archived content (verbatim) ---------------------------------
archived_notes_idx = [32, 33, 34, 35, 36, 37, 39]
archived_note_titles = {
    32: "QRESCE-0001 v0.5 brand-layer reframing (2026-05-18, ff82ce30)",
    33: "QRESCE-0001 v0.5 brand LOCKED at QorTroller (2026-05-18)",
    34: "Phase 2 R0 deep-verification (2026-05-18, 8bd82b0c)",
    35: "Phase 1 post-STABILITY-9 cleanup (2026-05-18, 9b2d8722)",
    36: "STABILITY-9 empirical closure (2026-05-18, cf1e64de + 756eb36a)",
    37: "Phase O1-D-PATH-B v1 complete (2026-05-17)",
    39: "Phase O1-D-AUTO-SUPERSEDE complete (2026-05-17)",
}
archived_table = [lines[i].rstrip("\r\n") for i in range(190, 270)]  # rows 229..109A

# ---- build wiki archive --------------------------------------------------
w = []
w.append("# CLAUDE.md Archive — 2026-05 NOTEs + Phase Summary rows (109A-229)\n")
w.append("\n")
w.append("> Lossless archive created 2026-05-22 by `scripts/_prune_claude_md_2026_05_22.py` "
         "to keep CLAUDE.md under Claude Code's performance threshold. Every entry below was "
         "moved **verbatim** out of CLAUDE.md and replaced there with a one-line pointer. "
         "Nothing was deleted from the protocol record; full per-commit narrative also lives "
         "in `git log --grep='NOTE:' -- CLAUDE.md`.\n")
w.append("\n")
w.append("## Archived NOTEs (7 completed arcs)\n")
w.append("\n")
for i in archived_notes_idx:
    w.append(f"### {archived_note_titles[i]}\n")
    w.append("\n")
    w.append(lines[i].rstrip("\r\n") + "\n")
    w.append("\n")
w.append("## Archived Phase Summary rows (Phase 109A through 229)\n")
w.append("\n")
w.append("Moved from the inline `## Phase Summary` table. Phase 230+ rows remain inline in "
         "CLAUDE.md; earlier Phase 17-229 narrative remains in "
         "`wiki/phases/phase_summary_archive_17_229.md`. Rows preserved here in original "
         "descending order (229 -> 109A).\n")
w.append("\n")
w.append("| Phase | Key milestone |\n")
w.append("|-------|---------------|\n")
for row in archived_table:
    w.append(row + "\n")
w.append("\n")
WIKI.parent.mkdir(parents=True, exist_ok=True)
WIKI.write_text("".join(w), encoding="utf-8")

# ---- build pruned CLAUDE.md ----------------------------------------------
note_pointer_block = (
    "NOTE: ARCHIVED 2026-05-22 (lossless) -- 6 completed-arc NOTEs moved verbatim to "
    "`wiki/phases/phase_archive_2026_05_notes_and_summary.md` to cut CLAUDE.md reload cost: "
    "(1) QRESCE-0001 v0.5 brand-layer reframing `ff82ce30` [memory: project_qresce_0001_v05_brand_reframing_shipped]; "
    "(2) QRESCE-0001 QorTroller brand LOCK [memory: project_qresce_0001_qortroller_lock]; "
    "(3) Phase 2 R0 deep-verification `8bd82b0c`; "
    "(4) Phase 1 post-STABILITY-9 cleanup `9b2d8722`; "
    "(5) STABILITY-9 empirical closure `cf1e64de`+`756eb36a` [memory: project_stability_9_empirical_closure; "
    "wiki/phases/phase_235_stability_9_closure.md]; "
    "(6) Phase O1-D-PATH-B v1 [superseded by v2; memory: project_phase_o1_d_path_b_v2_wired]. "
    "Full text in the wiki archive + `git log --grep='NOTE:' -- CLAUDE.md`." + NL
)
supersede_pointer = (
    "NOTE: ARCHIVED 2026-05-22 (lossless) -- Phase O1-D-AUTO-SUPERSEDE (VAPI-O3-SUPERSEDE-v1, "
    "11th FROZEN-v1 primitive, 2026-05-17) moved verbatim to "
    "`wiki/phases/phase_archive_2026_05_notes_and_summary.md`. Headline: 92-byte preimage "
    "`SHA-256(b\"VAPI-O3-SUPERSEDE-v1\"||...)` empirically supersedes the 504h shadow_age "
    "calendar gate; PV-CI 122->125. Full text: wiki archive + git history." + NL
)
table_pointer_row = (
    "| <=229 | _Phases 109A-229 archived 2026-05-22 to "
    "`wiki/phases/phase_archive_2026_05_notes_and_summary.md` (full per-phase detail preserved "
    "verbatim). Earlier Phase 17-229 narrative in `wiki/phases/phase_summary_archive_17_229.md`. "
    "Inline table below retains Phase 230+ only, per curation discipline._ |" + NL
)

out = []
for i, ln in enumerate(lines):
    if i == 32:
        out.append(note_pointer_block)
        continue
    if i in (33, 34, 35, 36, 37):
        continue
    if i == 39:
        out.append(supersede_pointer)
        continue
    if i == 190:
        out.append(table_pointer_row)
        continue
    if 191 <= i <= 269:
        continue
    out.append(ln)

new_text = "".join(out)
CLAUDE.write_text(new_text, encoding="utf-8")

print("OK")
print("wiki archive   :", WIKI.relative_to(ROOT), "->", len(WIKI.read_text(encoding='utf-8')), "chars")
print("CLAUDE.md before:", len(raw), "chars")
print("CLAUDE.md after :", len(new_text), "chars")
print("saved          :", len(raw) - len(new_text), "chars (~%d tokens)" % ((len(raw) - len(new_text)) // 4))
