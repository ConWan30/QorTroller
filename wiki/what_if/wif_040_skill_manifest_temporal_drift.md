# WIF-040 — Skill Manifest Temporal Drift

**Layer**: W3 (Meta-risk — risk to the skill system itself)
**First Identified**: Phase 211 autoresearch cycle (2026-04-14)
**Status**: STRUCTURALLY_CLOSED — Phase 212 COMPLETE (vapi.md Reference state replaced with MCP directive; vapi_skill_state_sync tool added to unified_server.py; MANDATORY_INVARIANTS #12 converted to MCP-range directive)

---

## W3-006 — Skill Manifest Temporal Drift

**Failure Mode**: The `/vapi` skill file (`~/.claude/commands/vapi.md`) embeds hard-coded
reference state (phase, test counts, agent fleet size, separation ratio, wallet balance) that
diverges from CLAUDE.md over time. At Phase 211, the embedded state was Phase 156 — a 55-phase
lag — causing every autoresearch evaluation and every ANALYSIS mode cite to produce stale values.

**Implication**:
- ANALYSIS mode cites wrong test counts (1868 vs 2268 bridge), wrong agent fleet (20 vs 36),
  wrong wallet balance (0.35 IOTX vs 20.432 IOTX) → incorrect deployment decisions
- MANDATORY_INVARIANTS check in autoresearch embeds stale test counts as correctness gate
- Pre-Execution Checklist item 12 (test count invariant) blocks legitimate code changes
  when it enforces wrong baseline counts
- BiometricPrivacyComplianceAgent listed as "PROPOSED, no code written" for 52 phases
  after it went LIVE as agent #22 (Phase 159)
- VAPISwarmOperatorGate.sol listed as "DEFERRED" for 81 phases after going LIVE (Phase 130)
- ALL_PAIRS P0 GATE section listed wrong blocker pair (P2vP3=0.401 vs P1vP3=0.032)
  for 14 phases, directing wrong capture protocol

**Detection**:
- Session startup STEP 2 compares skill embedded state vs CLAUDE.md — discrepancy flag
- Any phase number in Reference state section older than CLAUDE.md current phase by >3

**Mitigation Applied (2026-04-14)**:
- vapi.md updated: Phase 156→211, 1868→2268/468→482/265→452 bridge/Hardhat/SDK,
  39→43 contracts, 20→36 agents, wallet 0.35→20.432 IOTX, ALL_PAIRS P0 GATE
  P2vP3=0.401→P1vP3=0.032, Critical Gaps Phase 156→211 state,
  BiometricPrivacyComplianceAgent PROPOSED→LIVE, VAPISwarmOperatorGate DEFERRED→LIVE

**Structural Fix (COMPLETE — Phase 212)**:
- vapi.md Reference state section replaced with MCP directive: call `mcp__vapi__vapi_protocol_state`
  or `vapi_skill_state_sync` at session start; illustrative fallback marked "NOT authoritative"
- Skill is now a pure procedure + invariant document; no embedded numeric state that can drift
- MANDATORY_INVARIANTS check #12 converted: "verify via mcp__vapi__vapi_protocol_state or CLAUDE.md
  before any code change (nominal: ~2276 bridge / ~482 Hardhat / ~452 SDK)"
- ANALYSIS mode and Communication Style cite blocks redirected to MCP as authoritative source
- vapi_skill_state_sync tool (Tool 13) added to unified_server.py: detects drift, generates
  sync_block (paste-ready Reference state text), returns canonical_values from CLAUDE.md
- vapi_autonomous_gap_scan tool (Tool 17) added: Gap G-005 documents WIF-040 residual
  (STEP 2 Session Startup Protocol integration — future follow-up)

**Root Cause**:
- MCP autonomous sync (Phase 210) updated vapi-mcp/server.py and knowledge_server.py
  to parse CLAUDE.md live — but the skill file itself (`~/.claude/commands/vapi.md`)
  is outside the repo and was not included in the Phase 210 sync scope
- No automated check verified skill embedded state vs CLAUDE.md after each phase completion

**W3 Classification**: CORPUS META-RISK — the skill is the interface through which autoresearch
reads its own scoring rubric; stale embedded state corrupts scoring accuracy.

**Evidence**: Phase 211 session startup detected 55-phase lag; MCP vapi_protocol_state returned
Phase 211 / bridge=2268 / agents=36; vapi.md Reference state showed Phase 156 / bridge=1868 / agents=20.

**Phase Candidate for Structural Fix**: Phase 212 (no new tests required; skill-level doc change only)
**Effort**: ~1 hour
