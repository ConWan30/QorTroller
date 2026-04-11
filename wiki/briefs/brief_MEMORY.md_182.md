# VAPI Wiki Ingest Brief
Source: MEMORY.md | Phase 182 | 2026-04-09T23:22:59.993604+00:00
Provenance: [VAPI:Phase182:MEMORY.md:MEASURED]

## INSTRUCTION TO CLAUDE CODE
You are reading this brief to generate wiki pages. No API is called.
You are the intelligence layer. This engine handles file I/O only.

For each page listed below:
1. Read the source content at the bottom
2. Write the page to the path shown
3. Before writing: python vapi_wiki_engine.py check "<key sentences>"
4. After writing all pages: python vapi_wiki_engine.py snapshot --anchor

## Pre-Scan
Invariant violations in source: 0
  None detected

Metrics extracted:
{
  "sdk_tests": "728",
  "phase": "26"
}

Domains:
{
  "l4_calibration": true
}

## Pages To Create

- wiki/entities/l4_thresholds.md [TYPE: ENTITY]
  [VAPI:Phase182:VAPI_INVARIANTS.md:FROZEN]

## Provenance Rules
Every factual claim: [VAPI:Phase182:MEMORY.md:MEASURED]
Frozen constants: [VAPI:Phase182:VAPI_INVARIANTS.md:FROZEN]
Designed (not measured): [VAPI:Phase182:MEMORY.md:DESIGNED]
No provenance: tag [NEEDS_PROVENANCE]

## Frozen Values (never modify in wiki)
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
  "separation_gate": "0.70",
  "adjudication_registry": "0x44CF981f46a52ADE56476Ce894255954a7776fb4"
}

## Page Format
```markdown
# [TYPE]: [Entity Name]

[VAPI:Phase182:MEMORY.md:MEASURED]

## Current State
[description — cite provenance on every factual claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|

## Related Pages
- [[entity_1]]
```

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



## After Writing
python vapi_wiki_engine.py snapshot --anchor
python vapi_wiki_engine.py sync_what_if
python vapi_wiki_engine.py autoresearch_feed
