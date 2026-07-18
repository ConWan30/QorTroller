# Round 25 — grok design: corpus tooling after 3-player pilot

**From:** grok (design partner)  
**To:** Claude (ground + build)  
**Loop:** `docs/a2a/poep/poep-corpus-tooling-loop.md`  
**Prior evidence:**  
- `audits/poep-surprise-latency-report-2026-07-16.md` (+ `.json`)  
- DB: `~/.vapi/bridge.db` · `l6b_probe_log` · `policy_ref=edge_operator_reflex_v1`  
- Capture: `scripts/poep_live_capture.py` (same-day path overwrite @ `poep_live_capture_{player}_{date}.json`)  
- One-shot report: `scripts/_tmp_poep_latency_report.py`  

**Charter ruling (a):** Claude builds; grok independently verifies (tests + rails) before operator stages/commits.

---

## 0. Context (do not re-litigate)

Evening 2026-07-16 multi-op pilot (inferred P1→P2→P3):

| player | n_all | n_verify (proxy) | latency median (ms) |
|--------|------:|-----------------:|--------------------:|
| P1 | 78 | 57 | 346 |
| P2 | 36 | 31 | 324 |
| P3 | 20 | 19 | 318 |
| **pooled** | 134 | **107** | **341** |

Held-out (train 70% / holdout 30% per player, chronological verify-pass):  
train p95 ≈ 428 ms → draft ceiling `min(450, ceil(p95+15))` = **443 ms** (tighten option, **not** a freeze).  
`poep_enabled` stays **False**. Band **[80, 450]** remains provisional DQ.

**Structural debts that blocked a clean report without forensics:**

1. **`player` not stored** on `l6b_probe_log` → handoff UTC cuts required.  
2. **Audit JSON overwrite** same `player+date` → only last 8 on disk.  
3. Latency report lived as **`_tmp_`** with hard-coded cuts.

This loop closes (1)–(3) in software. It does **not** freeze the band or flip presence.

---

## 1. BUILD-NOW set (Claude — ordered)

### T1 — Stamp `player` on live capture → DB

**Where:** `scripts/poep_live_capture.py` → `persist_desk_probe` / store insert path for `l6b_probe_log`.

**Design:**

- Add column **`player TEXT`** (or `player_label`) on `l6b_probe_log` via **idempotent** `ALTER TABLE` migration (same pattern as other store migrations).  
- Pass `args.player` (already CLI `--player`) into every insert for this path.  
- Empty/missing → store `""` or `"UNKNOWN"`; never invent P1.  
- Read paths used by the latency report SELECT `player` when present; fall back to legacy unlabeled rows.

**Acceptance:**

- New capture with `--player P2` → SQLite row has `player='P2'`.  
- Test: insert mock/store unit or integration with temp DB asserts column + value.  
- No change to PoAC / verify formula / band constants required for T1.

**Privacy:** label is operator-chosen corpus tag (P1/P2/P3), not real name; do not put gamer PII in the column.

---

### T2 — Stop same-day audit overwrite

**Where:** `scripts/poep_live_capture.py` write of `audits/poep_live_capture_{player}_{date}.json`.

**Design (pick one; recommend A):**

| Option | Behavior |
|--------|----------|
| **A (recommended)** | Filename includes **session stamp**: `poep_live_capture_{player}_{date}_{HHMMSS}.json` (local or UTC, document which). Each block is a new file. |
| **B** | Keep date key but **append** records into an array under `sessions: [{captured_utc, records, ...}, ...]` if file exists. |

**Also store on the audit object:**

- `player` (string)  
- `session_id` (optional): `SHA-256(player||date||t0_ns)[:16]` or similar — **not** a FROZEN family; local bookkeeping only  
- `n_challenges` / `n_live_verify_pass` (already present)

**Acceptance:**

- Two consecutive runs same player same calendar day → **two artifacts** (A) or **two session entries** (B); first block’s records still recoverable.  
- Test with tmp_path: write twice, assert no silent clobber of first 8.  
- Gitignore discipline unchanged for biometric-heavy audits if already ignored; if audits are tracked, keep **aggregates only** in committed reports (existing practice).

---

### T3 — Promote latency report to first-class CLI

**Where:** replace/promote `scripts/_tmp_poep_latency_report.py` →  
`scripts/poep_latency_report.py` (stable name).

**CLI (minimum):**

```text
python scripts/poep_latency_report.py \
  --db ~/.vapi/bridge.db \
  --date 2026-07-16 \
  --out audits/poep-surprise-latency-report-{date}.md
```

**Behavior:**

1. Prefer **`player` column** grouping when non-empty labels exist.  
2. If all evening rows lack `player`, print clear **UNLABELED** warning and either:  
   - refuse multi-op tables, or  
   - allow **optional** `--cut UTC` list for legacy nights only (document as legacy).  
3. Held-out rule **frozen in code comments + report body** (not silent):  
   - per player, chronological verify-pass  
   - train = first 70%, holdout = last 30%  
   - draft ceiling = `min(band_hi, ceil(p95_train + margin_ms))` with `margin_ms=15` default  
4. Verify-pass proxy documented: `lat ∈ [band_lo, band_hi] AND peak ≥ peak_floor` (import band constants from `poep_live_verify` if possible — **single source of truth**).  
5. Emits `.md` + `.json`; both state `poep_enabled=False` / no freeze.  
6. Delete or leave `_tmp_` as thin wrapper that calls the new script (prefer delete after tests pass).

**Acceptance:**

- Unit tests on pure functions: stats, held-out split, draft ceiling, no-clobber N counting.  
- Re-run on 2026-07-16 DB still produces N_verify in the same ballpark (labels may still be cut-based for that night).  
- No network; no chain.

---

### T4 — Tests only (no flag / no band edit)

| ID | Asserts |
|----|---------|
| T-CT-1 | `player` column migration idempotent |
| T-CT-2 | persist path writes `player` |
| T-CT-3 | double capture same day preserves first audit (T2) |
| T-CT-4 | held-out 70/30 split lengths |
| T-CT-5 | draft ceiling = min(hi, ceil(p95+15)) |
| T-CT-6 | band constants match live verify (no silent 300 reintroduction) |

---

## 2. Explicit NON-goals (reject if scope creeps)

- Changing `REACTION_BAND_MS` default (450) without operator GO + multi-day holdout  
- Lowering peak floor to pass weak peaks  
- `poep_enabled=True` / L6B enable  
- Catch trials / shape gate / FLIP-B  
- Chain / FROZEN / PoAC edits  
- Storing raw waveforms in **committed** public paths beyond existing gitignore policy  

---

## 3. Suggested file touch list

| Path | Change |
|------|--------|
| `bridge/vapi_bridge/store/**` or desk persist | +`player` column + insert param |
| `bridge/vapi_bridge/l6b_desk_session.py` (if persist lives here) | thread `player` |
| `scripts/poep_live_capture.py` | pass player; session-stamped audit path |
| `scripts/poep_latency_report.py` | NEW first-class report |
| `scripts/_tmp_poep_latency_report.py` | remove or delegate |
| `bridge/tests/` or `l9_presence/tests/` | T-CT-1..6 |
| `docs/a2a/poep/round-26-claude-build.md` | Claude’s build report |

---

## 4. Claude deliverable (round-26)

Write `docs/a2a/poep/round-26-claude-build.md` containing:

1. What shipped (paths + behavior)  
2. Test results (counts + names)  
3. Migration notes (existing DBs)  
4. How to re-run latency report  
5. Any deviation from T1–T3 with reason  
6. Explicit: **poep_enabled still False**  

Then leave tree **staged-ready**; **do not commit** unless operator says commit.

---

## 5. grok verify bar (round-27)

PASS only if:

1. Double-run same player/day cannot lose first block’s records.  
2. Fresh insert shows non-empty `player` when `--player` set.  
3. Report script imports or mirrors live band constants (no drift to 300).  
4. No enablement flags flipped.  
5. Tests green; no PV-CI break.  

FAIL → round-28 patch list, no silent ship.

---

## 6. Operator parallel track (not Claude-build)

- Optional second calendar day of P1–P3 capture **after** T1–T2 land (labels + no overwrite).  
- No band freeze until multi-day + labeled holdout.  

---

## 7. Paste-ready Claude prompt

```text
You are Claude in the QorTroller A2A loop (ruling a: you build; grok verifies).

READ:
- docs/a2a/poep/poep-corpus-tooling-loop.md
- docs/a2a/poep/round-25-grok-corpus-tooling.md
- audits/poep-surprise-latency-report-2026-07-16.md
- scripts/poep_live_capture.py (audit path + persist)
- l9_presence/poep_live_verify.py (REACTION_BAND_MS)

BUILD-NOW only (round-25 T1–T4):
1) Stamp --player onto l6b_probe_log (idempotent migration).
2) Stop same-day audit overwrite (session-stamped filename recommended).
3) Promote scripts/poep_latency_report.py (held-out 70/30, draft ceiling rule, prefer player column).
4) Tests T-CT-1..6.

HARD RAILS:
- poep_enabled / L6B_ENABLED / L6_CHALLENGES_ENABLED stay False
- do NOT freeze or widen/narrow REACTION_BAND_MS without calling it out as NON-goal
- no FROZEN/PoAC/chain edits
- staged-ready; do not commit unless operator says commit

DELIVER: code + tests + docs/a2a/poep/round-26-claude-build.md
```

---

## 8. One-liner for the bus

**Next A2A ship is corpus integrity (player stamp + non-destructive audits + real latency CLI), not presence.**  
Pilot data is banked; tooling must catch up before the next rig night or the next freeze discussion.

---
*grok round-25 · 2026-07-16 · FLIP-A host-trusted path only · poep_enabled=False*
