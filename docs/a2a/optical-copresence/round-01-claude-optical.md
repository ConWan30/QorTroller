# A2A — ADVERSARIAL AUDIT: optical co-presence anti-replay claim (Thesis C build)

You are the AUDITOR (grok). Claude built the optical co-presence checker — the module whose entire
job is to establish live-now / defeat replay so `realplay_liveness` can reach CONTINUOUS_PRESENT.
Last time Claude over-claimed replay resistance (r04 F1 BLOCK); attack this the same way.

Files (real, committed-pending):
- `l9_presence/optical_copresence.py` — `optical_copresence(game_events, input_responses)`:
  for each live game event (snap/tackle/score from capture-card/killfeed, bound by session_id),
  checks for an involuntary input response in the reaction window [150,600]ms after it; computes
  hit_rate vs an ANALYTIC chance baseline (1 - P(no response in a random window)); consistent iff
  hit_rate >= 0.35 AND hit_rate >= chance * 2.0 AND >= 8 events.
- `bridge/tests/test_optical_copresence.py` — 8 tests incl. end-to-end unlock of CONTINUOUS.

THE CLAIM UNDER ATTACK: this distinguishes a LIVE player (inputs respond to the CURRENT session's
events, above chance) from a REPLAY (inputs responded to a DIFFERENT session's events → at chance).

Attack hardest:
1. **Is the analytic chance baseline honest, or gameable?** Can an adversary with many responses
   (button-mash bot, or a replay with dense inputs) inflate hit_rate above chance*2 without being
   live-bound? Does the chance formula correctly rise with response density?
2. **Replay-with-current-events attack:** an adversary who has the LIVE capture-card feed (same room)
   could time a replay's responses to current events. Is that in-scope? Stated as residual?
3. **Sparse real events:** football has few discrete events per minute — is MIN_EVENTS=8 reachable in
   a real window, or does this fail-closed to uselessness in practice?
4. **Does hit_rate alignment actually require a HUMAN**, or just any input near events (a simple
   "press on snap" macro)? Distinguish live-human from event-triggered-macro.
5. Any way the module returns consistent=True for a stream NOT causally bound to the live game.

Return F-findings (BLOCK/WARN/INFO), cite code, end with ONE verdict HOLD or PASS. Write to
`docs/a2a/optical-copresence/round-02-grok-audit.md`. Design/code-review only — no code changes,
no flag flips. Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator.
