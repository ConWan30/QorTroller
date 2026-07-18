# Cowork handoff — poep-gameplay-live (unblock HOLD)

**Why HOLD was correct:** public `origin/main` @ `4cddcc0` does not contain this arc.  
**Operator machine has sealed bodies.** This file is the paste/attach pack.

## Envelope pin

| Field | Value |
|-------|--------|
| envelope_id | `7096757871bd5c06` |
| body | `docs/a2a/poep/round-live-01-grok-open.md` |
| body_sha256 | `57503b651d728448471265ac42500eac5cd6a82d6bb0488531a808df45c76c8d` |
| prior | `docs/a2a/poep/poep-gameplay-live-design.md` |
| prior_sha256 | `441f023b3c84ec33615f6bdce806025a9be298ee2c92a6216f9e0e316051be74` |
| expect | `docs/a2a/poep/round-live-02-claude-build.md` |

## Attach these files from operator repo (fastest)

1. `docs/a2a/poep/poep-gameplay-live-design.md`
2. `docs/a2a/poep/round-live-01-grok-open.md`
3. `docs/a2a/poep/poep-gameplay-live-loop.md` (charter)
4. Optional: `docs/a2a/pkg/mailbox/outbox/7096757871bd5c06.json`
5. Strongly recommended for honesty model: `l9_presence/poep_gameplay_session.py` (round-04/05 PASS tree)

## After attach — mandate (unchanged)

```text
Arc: poep-gameplay-live
Ground against the attached design + LIVE-01 open (verify sha256 if envelope attached).
BUILD L1+L2 only per LIVE-01 section 1.
Dry must stay non-candidate (dry_plumbing_ok only; never presence_session_candidate_ok without live+bridge+seal).
MIN_GO_*=2, amplitude default 60 max 80, poep_enabled False.
No desk campaigns. No commit/push.
Write docs/a2a/poep/round-live-02-claude-build.md
```

## L1 / L2 decomposition (from design — sealed)

### L1 — Live session shell + seal + bridge activity (mockable)
1. `start-live`: mode=live, activity_source=bridge, live_seal = H(session_id||device_id||t_start||process_nonce)
2. Activity poll adapter: injected fetcher → classify_activity; only mark bridge when from adapter
3. Refuse challenges if not ACTIVE or PCC bad
4. Tests: dry non-candidate; live without seal no candidate; MENU no issue; seal round-trip

### L2 — Challenge driver
1. challenge-live: real fire at amplitude ≤80
2. Reuse fire primitive; document HID vs bridge ownership
3. Real verify_live_response + optional catch NO_GO
4. live_hardware=True only on real GO fire
5. CI: mock fire OK; real fire behind operator flag
6. Tests: clamp; NO_GO no force; candidate only when all live gates hold

### L3 — Operator dogfood (not agent-complete)

## Rails
poep_enabled/L6B/L6_CHALLENGES False · no FROZEN/PoAC/chain · sole committer = operator
