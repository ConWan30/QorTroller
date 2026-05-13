# Whitepaper v4 + README revamp — provenance pin (2026-05-13)

**Anchor commit (pre-revamp):** `e81e04aa` (Phase O4-VPM-INT close)
**Revamp commit:** to-be-assigned at landing as the next commit after `e81e04aa`
**Author:** VAPI Principal Architect
**Operator authorization:** "Make this a priority /goal... Utilize the necessary aligning /agent as well to create this as the masterpiece for understanding VAPI and final release white paper succeeding prior white paper drafts." + Plan-mode approval (`C:\Users\Contr\.claude\plans\rustling-soaring-rossum.md`) with four explicit decisions:
- Option A — Direct draft in main session (no background agent)
- License: Proprietary — All Rights Reserved
- Citation: Mint new Zenodo DOI for v4 at release
- Audience: All three (DePIN partners + tournament operators + academic researchers) equally

---

## What this revamp delivered

A single atomic documentation-only commit landing four files. **No code changes.** **Wallet-free.** **`CHAIN_SUBMISSION_PAUSED=true` held.** Mirrors the prior phase-close-commit ship shape.

### Files modified

**`README.md`** — Complete rewrite (Phase 41 → Phase O4 close state).

Pre-revamp content:
- 149 lines, ~6.2 KB
- Claimed 874 bridge tests / 13 LIVE contracts / separation ratio 0.362 (free-form baseline)
- Reflected Phase 41 protocol state — 168 phases out of date

Post-revamp content:
- ~250 lines
- States 3344 bridge tests / 49+ LIVE contracts / AIT separation ratio 1.199 N=37 (CLEARED) / touchpad_corners 0.728 (BLOCKER, honest disclosure)
- Phase O4-VPM-INTEGRATION close state with anchor commit `e81e04aa`
- All-audience framing (DePIN / operator / researcher) per plan §Operator-decisions
- Proprietary "All Rights Reserved" license posture per plan §Operator-decisions
- Citation block: v3 Zenodo DOI preserved; v4 citation path documented

### Files added

**`docs/vapi-whitepaper-v4.md`** — Canonical successor whitepaper.

- ~60 KB target met
- 17 sections + 2 appendices per plan §`docs/vapi-whitepaper-v4.md` structure
- Explicit "Supersedes v3" header with v3 Zenodo DOI preserved
- 13 sections cover post-v3 architecture not present in v3 (PATTERN-017 primitive family, Operator Initiative 3-agent fleet, Cedar v2, Layer 7 ZKBA artifact closure, VPM output layer, Anti-Hype Visual Grammar, PV-CI invariant gate, FSCA fleet signal coherence, marketplace, current calibration state, forward roadmap, architectural exclusivities)
- §14 "Current calibration state — honest" deliberately surfaces the touchpad_corners 0.728 BLOCKER and the four PITL calibration gates (L6, L6b, GSR, BT) that remain N=0 / closed
- §15 "What remains to be engineered" enumerates 10 forward-vector tiers distilled from CLAUDE.md NOTE entries
- §16 "What's exclusive to VAPI" is the architectural-exclusivity table from this session's protocol-position assessment

**`docs/WHITEPAPER_VERSIONING.md`** — Lineage doc (~50 lines).

- Maps v1 (paper/) → v2 → v3 (Zenodo DOI'd) → v4 (canonical successor)
- Citation guidance for external readers
- v4 Zenodo release plan

**`wiki/assessments/whitepaper_v4_revamp_provenance_2026-05-13.md`** — This file. Provenance pin.

---

## What each claim is sourced from

The whitepaper v4 makes specific quantitative claims. Each is sourced from an authoritative in-repo file at commit `e81e04aa`:

| Claim | Authoritative source |
|---|---|
| 49+ LIVE contracts | `contracts/deployed-addresses.json` |
| 38-agent autonomous fleet | `bridge/vapi_bridge/` agent module count + `CLAUDE.md` "fleet count" line |
| 77 PV-CI invariants | `.github/INVARIANTS_ALLOWLIST.json` entry count + `scripts/vapi_invariant_gate.py` |
| 26 FSCA contradiction rules | `bridge/vapi_bridge/fleet_signal_coherence_agent.py:CONTRADICTION_RULES` length |
| 7 ZKBA artifact classes | `scripts/zkba_compile_*.py` count + `bridge/vapi_bridge/zkba_artifact.py:ZKBAClass` enum |
| 6 active VPM compilers | `scripts/vpm_compile_*.py` count |
| 4 VPM draft manifests | `scripts/vpm_drafts/*.json` count |
| 3344 bridge tests | `python -m pytest bridge/tests/ --collect-only -q` + `CLAUDE.md` test-count line |
| 562 SDK tests | `python -m pytest sdk/tests/ -v` + `CLAUDE.md` |
| 528 Hardhat tests | `cd contracts && npx hardhat test` + `CLAUDE.md` |
| 26 frontend Vitest tests | `cd frontend && npm run test` + Phase O4 close commit body |
| AIT separation ratio 1.199 N=37 | `CLAUDE.md` "AIT corpus (Phase 231)" line + `bridge/vapi_bridge/store.py:get_ait_separation_status()` live state |
| touchpad_corners 0.728 N=35 | `CLAUDE.md` "Touchpad corners (superseded for primary gate)" line |
| tremor_resting 1.177 N=27 P1vP3=0.032 | `CLAUDE.md` "tremor_resting corpus" line |
| L4 thresholds 7.009 / 5.367 | `CLAUDE.md` "L4 Calibration State" section + Phase 57 commit reference |
| GIC_100 anchor tx | `CLAUDE.md` Phase 239 G3 NOTE entry + `0xe807347e...` block 43348052 |
| CORPUS-SNAPSHOT inaugural anchor | `CLAUDE.md` Phase 237.5 NOTE + `0x24e4ddb6...` |
| Cedar v2 Merkle roots | Phase O4 close commit body + `scripts/zkba_post_ceremony_audit.py:EXPECTED_MERKLES` |
| 3 Operator Initiative agentIds | Phase O0 closure NOTE + Sessions 1+2+3 Curator NOTE + `bridge/vapi_bridge/cedar_bundles/*.json` |
| CFSS 12-row lane matrix | `scripts/zkba_post_ceremony_audit.py:EXPECTED_LANE_MATRIX` |
| 10-element PATTERN-017 family | `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` Appendix B |
| Anti-Hype Visual Grammar 6 states | `scripts/vpm_visual_grammar.py:VISUAL_STATE_SIGNATURES` + `frontend/src/components/VpmGrammarVerifier.jsx:VISUAL_STATE_SIGNATURES_FROZEN` |
| Procedural Geometric Art v1 algorithm | `scripts/vpm_compile_market_listing.py:_compute_geometric_art_svg()` |
| 49 contract registry entries | `contracts/deployed-addresses.json` (51 contract slots; 49 substantive LIVE addresses) |
| Wallet balance ~15.03 IOTX | Sessions 1+2+3 close NOTE + Track 2 ceremony delta |
| VPM Registry §10 lifecycle ladder | `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` Appendix B §B.8 sub-gate roster |
| 10-commit Phase O4 roster | `git log e81e04aa~10..e81e04aa --oneline` |

---

## Deliberate exclusions

The following were **deliberately not** included in v4 to maintain protocol honesty:

1. **No mainnet deployment claims.** All current LIVE contracts are on IoTeX testnet (chain ID 4690). v4 is explicit about this.
2. **No "production-ready" tournament BLOCK enforcement claim.** Touchpad_corners battery has not closed; tournament BLOCK enforcement remains gated. v4 §14 surfaces this.
3. **No TGE date.** Token launch invariant ("no TGE before separation_ratio > 1.0 + all_pairs_above_1=True") remains in force. v4 §13 explicitly restates the invariant; no date is given.
4. **No partnership commitments.** Phase 99 deploy + LayerZero bridge mainnet + W3bstream applet registration are described as forward vectors, not commitments.
5. **No claim of L6 / L6b / GSR / BT detection capability.** All four layers are calibration-gated and currently disabled per CLAUDE.md "Hard Rules". v4 §3 + §14 surface this honestly.
6. **No claim of "first" beyond the protocol-architectural specifics empirically defensible.** Each "first" claim in v4 §16 cites the specific architectural construct (frozen-primitive ↔ frozen-compiler ↔ frozen-visual-grammar ↔ frozen-iframe-sandbox quadruple-bind; etc.).

---

## Verification

Pre-commit verification (executed before commit):

1. ✅ `README.md` modifications limited to full-file replacement; no other files in working tree affected outside the four planned deliverables
2. ✅ `docs/vapi-whitepaper-v4.md` size ~60 KB (matches plan target)
3. ✅ All commit hashes referenced (`e81e04aa`, `ece17f4f`, `0061e6d9`, `d5803d47`, `1b13618d`, `169471bb`, `7052144f`, `fd0d6699`, `524ae1cc`, `603c98cb`, `168256a0`, `0xe807347e...`, `0x24e4ddb6...`) verified extant via `git log --oneline` + `CLAUDE.md` references
4. ✅ All contract addresses cited verified against `contracts/deployed-addresses.json`
5. ✅ Test counts (3344 / 562 / 528 / 26) match `CLAUDE.md` post-Phase-O4-close values
6. ✅ Anti-Hype Visual Grammar 6-state matrix matches `scripts/vpm_visual_grammar.py:VISUAL_STATE_SIGNATURES`
7. ✅ Procedural Geometric Art v1 algorithm matches `scripts/vpm_compile_market_listing.py:_compute_geometric_art_svg()`
8. ✅ No accidental code changes — `git diff --stat` shows only `.md` files

---

## Commit shape (planned)

```
docs: VAPI public documentation revamp — README + Whitepaper v4 successor
```

Files staged:
- `README.md` (modified)
- `docs/vapi-whitepaper-v4.md` (new — canonical successor)
- `docs/WHITEPAPER_VERSIONING.md` (new — lineage doc)
- `wiki/assessments/whitepaper_v4_revamp_provenance_2026-05-13.md` (new — this file)

Counts at landing:
- Bridge / SDK / Hardhat / Contracts / PV-CI / FSCA: ALL UNCHANGED (docs-only commit)
- CHAIN_SUBMISSION_PAUSED: true held
- Wallet: 0 IOTX impact
- Anchor commit hint: `e81e04aa` (Phase O4 close ship)

---

*— VAPI Principal Architect, 2026-05-13*
