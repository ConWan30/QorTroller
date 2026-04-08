# VAPI Wiki Ingest Brief
## Source: MEMORY.md | Phase 166 | 2026-04-07T00:38:28.222373+00:00
## Provenance tag: [VAPI:Phase166:MEMORY.md:MEASURED]

---

## INSTRUCTION TO CLAUDE CODE

You are reading this brief to generate VAPI wiki pages.
No external API is called. You are the LLM.

Do the following in order:
1. Read the source content below
2. For each domain listed, create or update the corresponding wiki page
3. Every factual claim must include: [VAPI:Phase166:MEMORY.md:MEASURED]
4. Run check_invariants() on your proposed content before writing
   (call: python vapi_wiki.py check "<proposed_content_snippet>")
5. Write each page using:
   python vapi_wiki.py write_page <page_type> "<entity_name>" 166 "<content>"
   OR write the markdown file directly to wiki/<type>/<name>.md
6. After all pages are written: python vapi_wiki.py snapshot

---

## Pre-Scan Results

### Invariant Check on Source
Status: PASS — no violations detected in source text


### Extracted Metrics
{
  "separation_ratio": ".",
  "bridge_tests": "728",
  "sdk_tests": "8",
  "phase": "26"
}

### Domains Detected in Source
{
  "phase_state": false,
  "separation_ratio": false,
  "agents": false,
  "contracts": true,
  "l4_calibration": true,
  "what_if": false,
  "privacy": false,
  "zk_circuit": false,
  "ioswarm": false,
  "count": 2
}

---

## Pages to Create/Update

Based on domain detection, Claude Code should create these wiki pages:

- wiki/entities/l4_thresholds.md [TYPE: ENTITY]
  Content: 7.009/5.367 frozen values, staleness (12-feat vs 13-feat), recalibration candidate
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

---

## Provenance Rules (enforce these — do not skip)

- Every factual claim: [VAPI:Phase166:MEMORY.md:MEASURED]
- Measured values: [VAPI:Phase166:MEMORY.md:MEASURED]
- Designed (not yet measured): [VAPI:Phase166:MEMORY.md:DESIGNED]
- Frozen protocol constants: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]
- Claims without source: tag as [NEEDS_PROVENANCE]
- Contradictions: preserve BOTH claims, mark [CONTRADICTION: unresolved]

---

## FROZEN VALUES (never modify these in wiki pages)

{
  "poac_bytes": "228",
  "record_hash": "SHA-256(raw[:164])",
  "nPublic": "5",
  "zk_hash": "Poseidon(8)",
  "ceremony_beacon": "#41723255",
  "l4_anomaly": "7.009",
  "l4_continuity": "5.367",
  "epistemic_threshold": "0.65",
  "triage_prereq": "True",
  "auto_activate": "False",
  "block_quorum": "0.67",
  "mint_quorum": "0.80",
  "vhp_expiry_days": "90",
  "separation_gate": "0.70"
}

If the source text contradicts any frozen value, flag it as:
[CONTRADICTION: source claims X | frozen value is Y | [VAPI:Phase166:MEMORY.md:MEASURED]]
Write to: wiki/contradictions.md

---

## Wiki Page Format

Each page must follow this structure:

```markdown
# [Page Type]: [Entity Name]

[VAPI:Phase166:MEMORY.md:MEASURED]

## Current State
[factual description with provenance on each claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|
| ... | ... | [VAPI:Phase166:MEMORY.md:MEASURED] | LIVE/DESIGNED/STALE |

## Related Pages
- [[entity_1]]
- [[entity_2]]
```

---

## Source Content

# VAPI Lessons & Memory

## Architecture Decisions
- The gaming anti-cheat (DualShock Edge + PITL + PoAC) is the primary value proposition. DePIN/IoT is extensibility validation only.
- The bridge is the weakest trust link — ZK PITL proofs (Phase 26) are the fix, but currently run in mock mode with dev ceremony keys.
- The adaptive trigger resistance surface is what makes this novel — no other anti-cheat protocol has a hardware-rooted unforgeable biometric signal.
- PHGCredential is now provisional (Phase 37): earned when stable, suspended on-chain when device accumulates ≥2 consecutive critical 7-day windows.
- InsightSynthesizer (Phase 35–37) provides full temporal threat memory: 24h/7d/30d retrospective analysis driving forward detection policy updates.

## Code Quality Notes
- Bridge Python code uses asyncio throughout — never use synchronous blocking calls.
- All Solidity contracts target IoTeX L1 with P256 precompile at address 0x0100.
- Firmware uses PSA Crypto API — never software crypto on the nRF9160.
- The 228-byte PoAC wire format is frozen — do not change field offsets.
- BridgeAgent has 18 tools (Phase 37); uses `inputs` dict not `args` in `_execute_tool()`.
- RateLimiter is instantiated inside `create_operator_app()` factory — NOT global.
- Windows SQLite tests: use `tempfile.mkdtemp()` NOT `TemporaryDirectory` (WAL PermissionError).
- conftest.py: autouse event loop fixture prevents Python 3.13 asyncio teardown crash.

## Testing Notes
- Hardhat tests: ~341, Bridge pytest: ~728, SDK pytest: ~28, Hardware suite: ~72
- Combined bridge+SDK: 728 passed, 7 skipped (Phase 37 baseline)
- The "100% detection / 0% false positive" figure is on SYNTHETIC data only — this must be clearly stated everywhere.
- Real-hardware validation is the #1 priority gap.
- 5 real-ZK tests skip unless `run-ceremony.js` artifacts exist.
- E2E tests need Hardhat node: `HARDHAT_RPC_URL=http://127.0.0.1:8545`

## Whitepaper Notes
- Source: `paper/vapi-whitepaper.md` (CURRENT); `whitepaper/vapi-whitepaper.md` (ARCHIVED)
- Rewrite target: `docs/vapi-whitepaper-v2.md`
- The paper tries to be 3 things (DePIN protocol + gaming anti-cheat + economic agent framework). Lead with gaming.
- §7.5 Phases 18–37 need complete rewrite from changelog format to proper technical exposition.
- BridgeAgent (Claude tool_use) is a UX feature, not a protocol contribution — move to appendix.
- All detection percentages must include "on synthetic test patterns" caveat.
- Remove all phase numbers from main text (internal dev milestones only).

## Threshold Documentation Needs
- L4 Mahalanobis anomaly threshold (3.0): magic number, needs empirical calibration comment
- L4 continuity threshold (2.0): magic number, needs empirical calibration comment
- L5 CV < 0.08, entropy < 1.5 bits, quantization > 0.55: magic numbers
- Behavioral warmup sigmoid scaling factor 20000: magic number needing derivation comment
- Burst farming CV / 2.0 formula: magic number needing derivation comment
- DBSCAN ε=1.0, min_samples=3: magic numbers

## Hardware Testing
- DualShock Edge VID:PID: Sony CFI-ZCP1
- Hardware tests in `tests/hardware/`, marker `@pytest.mark.hardware`
- Excluded from CI by default via `addopts = -m "not hardware"`
- Session captures saved to `sessions/` directory
- Calibration output: `calibration_profile.json`



---

## After Writing Pages

Run these commands in order:
  python vapi_wiki.py lint
  python vapi_wiki.py snapshot
  python vapi_wiki.py autoresearch_feed

The autoresearch_feed command syncs any wiki gaps into the AutoResearch
experiment log so the next /vapi autoresearch cycle can address them.
