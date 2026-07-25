# Context Note — Vocabulary Discipline + Reframed Next Focus (2026-07-25)

> **STATUS:** A context note authored after Match 3 of the second-human grind.
> The arc that produced this: today's Matches 2 + 3 (NCAA CFB 27) surfaced a
> language-vs-reality gap in how the agent was framing the protocol's
> integrity claim. The operator flagged it directly — "your language needs
> to be differentiated regarding the two types of games, you are still using
> terminology aimed at Warzone style of gameplay instead of football." This
> file captures the corrected frame going forward. NOT a marketing change;
> a load-bearing distinction about what the protocol actually measures.

## The language-vs-reality gap

The `qortroller.py` authorship lane was designed for Call of Duty: Warzone.
Every variable is kill-literal:

- `authored_kills`, `witnessed_own_kills`, `count_witnessed_own_kills`
- `kill_event(killer, victim, t)`
- `"authored kills are R2-bound on the KAS path (design invariant of the
  authorship chain)"`
- Recall denominator = killfeed OCR

Warzone has a killfeed — killer + victim are real in-game entities that an
OCR pass on the screen HUD can read and attribute to a player handle. NCAA
CFB 27 has no killfeed. It has a scoreboard. There is no in-game HUD element
in a football game that says "player 2 stiff-armed defender X on play Y" the
way Warzone says "player 2 eliminated player X." The `kill_event` lane is
structurally shooter-only and has no football analog.

## What the honest signals from Matches 2 + 3 actually mean

The `authored=0 / witnessed=None` honest-null across two consecutive real
NCAA CFB 27 matches is not purely the dual-connection topology constraint —
it is ALSO sport-mismatched. Even with perfect topology (single-HID ring),
a kill OCR pass reading a NCAA scoreboard would produce zero authored
football outcomes, because there are no authored football outcomes for the
killfeed lane to produce. The lane is running a shooter-only primitive
against a football game and getting nothing — that "nothing" is being read
as "the protocol failed to prove kills" when it actually means "the
protocol ran the wrong primitive for this sport."

Match 3's `kf_verdict: SPECTATED_NOT_AUTHORED / kf_other_kills: 3` is the
killfeed lane reading a football HUD and producing a structurally-only-
possible verdict. It can NEVER produce `authored > 0` against a football HUD
because the input — killfeed OCR — doesn't exist for football.

## What the protocol actually demonstrates, in football vocabulary

The football-appropriate integrity claim is presence + retina-perceived
gameplay, NOT authored kills. Two lanes:

### Presence (sport-agnostic) — `SYNCHRONIZED_CONTROLLER`

Defined at `l9_presence/controller_presence.py`. The chain:
- born (VMDR — manufacturer-registered device, pubkey hashed)
- owned (ioID — the certified Edge is registered on IoTeX as gamer's
  device, gamer-self wallet pattern; e.g. ioID 498 / TBA 0xFCee2377)
- present-candidate (PoEP gameplay-live — reflex probe fired-and-
  IMU-corroborated by the single-HID ring reader)
- session-joined (PoSP — the session has a fresh `session_id`, retina
  perception root anchored)

`SYNCHRONIZED_CONTROLLER` proves: "for one device_id, an ioID-registered
gamer was cryptographically bound to a controller AND a real-time reflex
probe was fired-and-IMU-corroborated in a single HID reader." None of this
is kill-concept. For football that translates to: "the certified Edge was
in player 2's hands during this session, player 2's IMU produced
corroborated reflex responses to nonce-bound haptic probes from the
bridge, the device's ioID binding is intact."

The IDEA.md sentence "proving a real human was at the controller" maps
cleanly to SYNCHRONIZED_CONTROLLER. The IDEA.md sentence "that their
trigger pulls caused the kills on screen" does NOT map to football at all
— that claim is structurally shooter-only.

### Retina perceived gameplay (sport-agnostic) — `PoSP SYNCHRONIZED`

Match 3 produced `PoSP SYNCHRONIZED fusion_rows=142 retina_root=fd3d4535`
vs Match 2's `(no record)` honest-null. The retina perception lane
promoted 113 live perception rows (5803 events) into a temporal-beacon-
anchored root. That is sport-agnostic — it's the retina pipeline SEEING
gameplay and sealing a perception root, with no sport-specific ontology
of what the gameplay IS.

Paired with SYNCHRONIZED_CONTROLLER, the honest football claim becomes:
"a verifiable human was at the certified controller, in real gameplay,
AND the retina perceived that gameplay." That pairs cleanly with the
protocol's integrity thesis for NCAA CFB 27 — a claim about WHO was
present and WHAT they did, not which defender they tackled.

## What this note changes going forward

### Vocabulary discipline

When working on football (GAME_PROFILE_ID starts with `ncaa_cfb_`):
- "presence" not "authorship"
- "IMU-corroborated reflex" not "R2-kill causal promotion"
- "retina perceived gameplay" not "witnessed killfeed"
- "PoSP fusion_rows" not "witnessed kills"
- "SYNCHRONIZED_CONTROLLER" not "authored > 0"

When working on shooters (cod_warzone etc.): the killfeed vocabulary
stays — it IS structurally the right primitive there. The killfeed lane
is shooter-correct, not universally-correct.

### Footgun to avoid

The killfeed honest-nulls (`authored=0 / witnessed=None`) in NCAA matches
will continue appearing in receipts until the killfeed lane is gated off
for football. Treating those nulls as "the protocol needs to close the
authorship gap" was MY mistake — they're actually "the protocol ran the
wrong primitive for this sport." This is a real reframing, not cosmetic
relabeling. The follow-up to disable killfeed OCR for football profiles
(`RETINA_KILLFEED_ENABLED=false` conditional on game_profile_id) is not
"premature polish" — it's integrity framing cleanup.

### Reframed next-focus arc

**Land the SYNCHRONIZED_CONTROLLER verdict under the second human via the
PoEP single-HID bridge fire+IMU ring under the campaign exception — and
pair it with the retina-promoted PoSP signal Match 3 already demonstrated —
to produce the first honest football-presence receipt.**

The goal is NOT to produce `authored > 0` (a Warzone concept that doesn't
translate to football). The goal is to produce `SYNCHRONIZED_CONTROLLER`
paired with the existing retina-perception signal — which IS the
football-appropriate integrity thesis.

If the arc succeeds, the project has its first honest football-presence
receipt against a second human. If it fails (the dual-writer conflict can't
be resolved without a hardware redesign), the project learns honestly that
SYNCHRONIZED_CONTROLLER isn't rig-reachable under dual-connection, and the
honest football deliverable is PoSP-only (retina-perceived gameplay without
controller-presence proof). Either outcome is a real, valuable result.

## What this note explicitly does NOT do

- Does NOT undo the killfeed architecture. The `kill_event` / KAS path is
  structurally correct for shooters and stays defined. The fix is GATING
  the killfeed lane off when GAME_PROFILE_ID is football-shaped, not
  deleting it.
- Does NOT re-grade the IDEA.md pitch. The pitch says "proving a real
  human was at the controller AND that their trigger pulls caused the kills
  on screen." The first half claims presence (SYNCHRONIZED_CONTROLLER,
  football-appropriate). The second half claims authored kills (killfeed,
  shooter-only). Both claims are technically honest for a shooter demo; the
  football-equivalent pitch needs the second claim replaced with "retina
  perceived gameplay." That's an operator-level decision, not this agent's
  to make.
- Does NOT commit to shipping SYNCHRONIZED_CONTROLLER. The dual-writer
  conflict and the `l6b_enabled` N>=50 hard-gate may be structurally
  unreachable on this rig; if so, the honest deliverable changes. The next
  focus is to DIG IN to find out, not to ASSERT it works.
- Does NOT modify FROZEN invariants, the PoAC wire format, or the
 228-byte record. PV-CI baseline unchanged.

## Signed

Authored by the agent (Claude Code session 2026-07-25), with operator
correction mid-conversation that surfaced the language-vs-reality gap.
The operator's exact words: "your language needs to be differentiated
regarding the two type of games, you are still using terminology aimed at
warzone style of gameplay instead of football, which i feel may be
causing mix up in context for your understanding based on what the
codebase honestly tells." Verified — it was.
