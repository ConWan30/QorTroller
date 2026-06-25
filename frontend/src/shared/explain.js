// Plain-language explainers for every complex QorTroller concept a gamer meets.
// Each entry: what it is / why it matters to YOU / the honest limit. The honest-limit
// line is mandatory — it's the same anti-overclaim discipline as the rest of the protocol,
// applied to the words. Keyed by short term; consumed by <ExplainChip term="..." />.

export const EXPLAIN = {
  poac: {
    title: 'PoAC — Proof of Autonomous Cognition',
    is: 'A tiny signed record your controller produces for each moment of play.',
    you: 'It is the evidence that a real human (you) made these inputs — not a bot or a script.',
    limit: 'It proves a live human acted; it is not by itself a claim about who you are.',
  },
  pitl: {
    title: 'PITL — the nine-level check stack',
    is: 'Layered checks (gravity, timing, biometrics, rhythm) that look at how you play.',
    you: 'Cheating cannot fake all of them at once, so honest play is what passes.',
    limit: 'Most layers are advisory; only a few hard signals block tournament eligibility.',
  },
  pocp: {
    title: 'Causal presence (PoCP / L9)',
    is: 'A check that your stick movements actually drive what happens on screen.',
    you: 'It shows you are physically here and in control, right now — not relayed or replayed.',
    limit: 'Validated, but not yet strong enough alone to be a tournament-grade verdict.',
  },
  recency: {
    title: 'Recency-bound presence',
    is: 'Your live presence tied to a recent blockchain beacon so it cannot be backdated.',
    you: 'Nobody can take an old session and replay it as if it happened now.',
    limit: 'It strengthens an existing presence signal; it does not create a standalone one.',
  },
  forcecurve: {
    title: 'Adaptive-trigger force-curve',
    is: 'The exact way your fingers press the adaptive triggers, measured ~1000x/second.',
    you: 'It is the hardest thing for cheat hardware to fake — your biomechanical signature.',
    limit: 'Used for live presence; cross-session identity needs a study not yet done.',
  },
  consent: {
    title: 'Consent — your keys, your data',
    is: 'Switches for what your gameplay data may be used for (tournament, research, market).',
    you: 'You grant and revoke each one with your own wallet. The bridge cannot do it for you.',
    limit: 'On-chain consent is signed by your wallet only; the bridge can read it, never set it.',
  },
  zkba: {
    title: 'ZKBA — zero-knowledge cards',
    is: 'Shareable proof cards that confirm a fact without exposing your raw biometric data.',
    you: 'You can prove "eligible" or "verified human" without handing over the underlying data.',
    limit: 'Each card states its own proof weight; not all carry the same strength.',
  },
  gic: {
    title: 'GIC — Grind Integrity Chain',
    is: 'A tamper-evident chain linking your verified sessions in order.',
    you: 'It is the running receipt that your play history has not been altered.',
    limit: 'It records cognitive-session continuity, not a ranking or a skill score.',
  },
  quadrille: {
    title: 'Provenance quadrille',
    is: 'A single seal that four independent integrity chains all check out together.',
    you: 'One honest "everything lines up" stamp across your play, the device, and the system.',
    limit: 'The seal is computed locally; putting it on-chain is a separate, deliberate step.',
  },
  vpm: {
    title: 'Honesty labels (VPM)',
    is: 'The rule that this app can only show a state the protocol can actually prove.',
    you: 'A green "live" light here is never decoration — it means the proof really passed.',
    limit: 'If something is unproven you will see it greyed or warning-banded, on purpose.',
  },
  bcra: {
    title: 'Connection readiness',
    is: 'A combined view of four links: your controller, the agents, the chain, and operations.',
    you: 'One honest light tells you whether you are fully connected and proven, or not.',
    limit: 'If any link is degraded or unknown, the overall state will not read as live.',
  },
}

export function explainFor(term) {
  if (typeof term !== 'string') return null
  return EXPLAIN[term.toLowerCase()] || null
}
