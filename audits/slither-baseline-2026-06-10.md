# Slither Baseline — 2026-06-10

**DECON-1 Stream 1 deliverable.** Slither CI gate at `.github/workflows/slither.yml` runs report-only and uploads `slither-latest.{json,md}` as a 90-day artifact. This file is the triage scaffold operator populates with the artifact's findings.

**Local baseline generation gated by Windows env (F-DECON-1.X):** `pip install slither-analyzer==0.10.4 solc-select==1.0.4` failed on the operator machine with `Failed to build installable wheels for ckzg` (a slither transitive dependency that needs a C compiler / specific wheel availability that the bundled Windows MSVC build did not satisfy). The CI pipeline (Ubuntu) is the authoritative source for the JSON baseline; operator downloads `slither-report-<commit-sha>` artifact from the GitHub Actions workflow run, runs `jq -r '.results.detectors[] | "\(.impact)|\(.check)|\(.elements[0].source_mapping.filename_relative):\(.elements[0].source_mapping.lines[0])|\(.description)"' slither-latest.json | sort -u` against it, and pastes the triage rows below.

**Scope:** `contracts/contracts/*.sol` (80 files) MINUS the `slither.config.json` filter (`node_modules|Mock|mock|test/|tests/|circuits/` — production contracts only).

---

## D-DECON-1 — Enforcement posture (provisional default)

Per the master plan's recommendation (a): **fail CI on NEW high-severity findings only; baseline suppressed via `slither.db.json`**. Implementation deferred to a follow-up commit after operator triages the JSON below; the workflow stays `continue-on-error: true` until then.

To activate the chosen posture once the JSON triage is complete:
1. Update `.github/workflows/slither.yml`: remove `continue-on-error: true` from the slither job.
2. Add `slither.db.json` to `contracts/` containing the baseline checksums (slither writes this automatically with `--triage-mode` or via `slither-format`).
3. Re-run on a fresh PR; only NEW high-severity findings should fail CI.

**Alternative postures** if operator amends D-DECON-1:
- (b) fail on medium+ — wider net, more false positives.
- (c) report-only permanent — keeps `continue-on-error: true`; no policy gate ever.

---

## Triage table (populate after first CI artifact download)

| Severity | Detector | File:Line | Triage | Note |
|---|---|---|---|---|
| HIGH | (e.g.) reentrancy-eth | `Foo.sol:42` | (TP / FP / AR) | (rationale; if TP → file phase ticket) |
| MEDIUM | … | … | … | … |
| LOW | … | … | … | … |
| INFO | … | … | … | … |

**Triage codes:**
- **TP** — true positive; file as a candidate phase for fix (out of DECON-1 scope per Stream 1 spec).
- **FP** — false positive; document the structural reason (e.g., low-level call in PoAC precompile path is intentional).
- **AR** — accepted risk; explicit operator decision to accept, with the reason recorded inline.

Each TP becomes a Phase XYZ scheduling item — DECON-1 Stream 1 does NOT auto-fix Solidity findings (the prompt's hard rule).

---

## Reproducing CI baseline locally (non-Windows)

```bash
# Linux / macOS / WSL — Windows currently blocked by ckzg wheel build
pip install slither-analyzer==0.10.4 solc-select==1.0.4
solc-select install 0.8.20 && solc-select use 0.8.20
cd contracts && npm ci
slither . --config-file slither.config.json \
  --json ../audits/slither-latest.json \
  --checklist > ../audits/slither-latest.md

# Convert JSON to triage rows
jq -r '.results.detectors[] | "\(.impact)|\(.check)|\(.elements[0].source_mapping.filename_relative):\(.elements[0].source_mapping.lines[0])|\(.description)"' \
  audits/slither-latest.json | sort -u > audits/slither-triage-rows.txt
```

---

**Stream 1 status:** Workflow + config + baseline scaffold all on `main`. First CI run on push `09d511ef` (or later) produces the artifact. After artifact triage, a follow-on commit lands the populated triage table + the D-DECON-1 enforcement posture switch.
