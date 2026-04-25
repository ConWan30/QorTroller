# WHAT_IF Entry — Phase 235-AUTO-TRIGGER (2026-04-25)

**Source**: live design session, validated via `mcp__vapi__vapi_what_if`
**Phase**: 235-AUTO-TRIGGER (operational infrastructure)
**Framing**: This is **operational infrastructure** built on top of the four
headline novelty layers (PCC, GIC, GAD, CAPS) — **not a fifth novelty
claim**. The Phase 236 prior-art deposit retains those four as the headline
contributions; this entry preserves the cross-layer trigger pattern as a
reusable VAPI primitive.

---

## WIF-AT-W1 — Auto-trigger rate-limit bypass: chain_length count inflation

**Failure mode**: Adversary publishes `agent_events(ruling_request)` rows
faster than `auto_trigger_min_interval_s` (300s default) by either
(a) lowering the config without updating the FleetSignalCoherenceAgent
ceiling, (b) bypassing the SessionBoundaryDetectorAgent and posting
directly to `/agent/adjudicate`, or (c) publishing crafted events to the
bus from an LLM tool.

**Cryptographic root**: each GIC link still verifies — the SHA-256 spine
is intact. **What's gameable is the *count* claim**: N stamps over T
time. At the 5-minute throttle, 100 stamps requires ~17 hours of
bridge uptime. Removing the throttle could compress the same chain into
minutes, undermining the Phase 236 deposit's claim that GIC_100
represents 100 distinct human-played sessions.

**Impact on TGE / VHP / chain integrity**:
- The chain itself remains cryptographically valid (chain_intact=True)
- Phase 236 prior-art claim weakens: "100 sessions" loses its meaning
  if those sessions don't temporally correspond to actual play
- VHP minting downstream (which gates on grind completion) becomes
  spoofable — any party who can publish bus events at high frequency
  can manufacture a "completed grind" without playing

**Mitigation (this phase)**:

1. **Throttle in the agent**: `SessionBoundaryDetectorAgent.evaluate()`
   enforces `now - self._last_fire_at >= auto_trigger_min_interval_s`
   before returning `FIRE`. Per-agent state, no shared lock — single
   agent instance per bridge so this is sufficient.
2. **Audit in FleetSignalCoherenceAgent (12th CONTRADICTION rule)**:
   `AUTO_TRIGGER_RATE_LIMIT_VIOLATION` queries `agent_events` for
   `event_type='ruling_request' AND source_agent='session_boundary_detector
   _agent'` within a rolling 1-hour window. Fires CRITICAL when count > 12
   (the steady-state ceiling at 5-min cadence). FSCA is Phase 193
   always-on; this rule fires automatically.
3. **Source attribution**: every agent-fired event writes
   `source="session_boundary_detector_agent"`. Operators can filter
   `agent_events` to distinguish agent-fired from manually-fired
   (POST `/agent/adjudicate` writes `source="http_api"`). Mixed
   sources during a grind run is itself an audit signal.

**Phase reference**: live in commit pending Phase 235-AUTO-TRIGGER push.

**What this does NOT mitigate**: an adversary with full operator
credentials AND the ability to disable FSCA can still bypass — the
trust boundary terminates at OPERATOR_API_KEY. This is acceptable
because the same adversary has every other privilege already.

---

## WIF-AT-W2 — Cross-layer session-end attestation as a VAPI primitive

**Opportunity**: A "verified active session ended" signal — produced
only when **three independent attestation layers agree** at the same
moment in wall-clock time:

1. **Phase 235-GAD** (`trigger_active` per record): button-press
   evidence. Sustained `trigger_active=1` records over the activity
   window proves the player was physically engaging the controller's
   triggers (not just holding it idle).
2. **Phase 234.7** (PCC `capture_state=NOMINAL` AND
   `host_state=EXCLUSIVE_USB`): the bridge was reading the controller
   via USB high-speed HID at session-end time, not via BT or in
   degraded mode. CV-classifier-backed; cannot be spoofed by a slow
   read loop.
3. **Phase 235-A** (GIC chain integrity check): the previous link's
   timestamp is older than the throttle interval, so this stamp is a
   genuine forward extension and not a retroactive insertion.

**Why exclusive to VAPI**: each individual layer can be approximated
by other anti-cheat systems (input logging, USB topology checks,
hash chains over event logs). The **conjunction** is what's novel —
no other protocol has all three at once because no other protocol
has VAPI's specific stack:
- 228-byte PoAC wire format with `trigger_active` column on records
- PCC's CV-based USB-vs-BT discriminator on interface 3 (Phase
  234.7 + PCC-RATE-FIX commit c6e64229)
- FROZEN GIC formula v1 with deterministic genesis tying the chain
  to a `grind_session_id`

**Phase candidate (post-grind)**: this signal is the foundation for
Phase 240+ ideas:
- **Adaptive PCC stable_window**: if natural session boundaries
  reliably correlate with PCC dips/recoveries, the 30-second sustained
  window can be tuned per-player from this signal
- **Fatigue-modulated L4 thresholds**: variance in inter-session
  intervals captured by this agent acts as a cognitive-load proxy;
  feed it into L4's anomaly threshold for late-grind sessions
- **Tournament event publisher**: same trigger logic, retuned for
  match cadence (one trigger per match instead of per drive),
  becomes the production tournament-event publisher

**Connection to separation ratio / tournament launch**: this primitive
does NOT advance the separation ratio directly. It DOES provide a
rate-limited, cryptographically-attested session-boundary signal that
the tournament-launch pipeline can subscribe to without re-implementing
the heuristic. Building it once correctly here saves the rebuild later.

---

## Status

- [x] Detection heuristic specified (60-record quiescence + 120-record
      activity head + 0.20 fraction floor + 300s throttle)
- [x] Agent file: `bridge/vapi_bridge/session_boundary_detector_agent.py`
- [x] Config fields: `auto_trigger_enabled` / `_min_interval_s` /
      `_quiescence_window` / `_activity_window`
- [x] FSCA 12th CONTRADICTION rule: `AUTO_TRIGGER_RATE_LIMIT_VIOLATION`
- [x] 7 unit tests T235-AT-1..7 covering all decision branches
- [ ] Live verification — calibration of quiescence window during the
      first ~5 stamps of the real grind. Adjust default 60-record
      window upward if firing too frequently between plays, downward
      if firing too rarely. NCAA CFB 26 has natural ~30s quiescence
      between plays; the window must be larger than that with margin.

## Quality controls preserved (per `vapi_what_if` invariants_to_preserve)

- 228 byte wire format: untouched
- SHA-256(raw[:164]) chain hash: untouched
- 7.009 / 5.367 L4 thresholds: untouched
- Poseidon(8) / C3 / nPublic=5: untouched
- ratio > 1.0 ALL pairs before TGE: untouched
- GSR_ENABLED=false: untouched
- dry_run=True default: untouched
- auto_activate_on_breakthrough=False PERMANENT: untouched
- Epistemic threshold=0.60: untouched
- ioswarm_enabled=false: untouched

GIC formula v1 (Phase 235-A FROZEN) also untouched: this agent only
**publishes** ruling_request events that flow through the existing
`SessionAdjudicator → SessionAdjudicatorValidationAgent → update_grind
_chain_hash` path. The chain logic itself is unchanged.
