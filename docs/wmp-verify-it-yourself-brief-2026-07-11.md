# QorTroller — Verify the Data Economy Yourself (zero trust)

**For a grant reviewer, an AI lab, or a data partner.** QorTroller turns a real, consented gaming
session into a *certified-human action-demonstration* that anyone can verify **without trusting
QorTroller** — and lets the gamer control exactly what leaves their hands. This page lets you confirm
that end-to-end from a fresh clone, in one command, with nothing installed.

> **The thesis, in one line:** gamers are the *Core Controllers of their gaming data* — the physical
> input source (the controller) is the cryptographic agency-holder over the data it produces.

## Verify it — one command, zero dependencies

The offline verifier is **pure Python standard library** — no `pip install`, no Node, no network:

```bash
git clone https://github.com/ConWan30/QorTroller && cd QorTroller
python scripts/verify_wmp_ladder.py
```

You'll see each rung of the data-economy ladder checked over the **real published session bundle**
(`wmp_corpus_real/wmp_corpus.jsonl`), ending in a verdict. Exit code 0 = every offline rung passed or
was honestly deferred.

## What each rung proves

| # | rung | what you're confirming, zero-trust |
|---|------|-----------------------------------|
| 1 | **Certified bundle** | the export is action-only, biometric-absent, macro-intent — and its payload is *scanned* for forbidden biometric columns, not just *claimed* clean |
| 2 | **Verifier hardening (AH-1)** | we forged our own certified data three ways; the verifier catches all three — including one case that was a **real gap we found in our own verifier and fixed** |
| 3 | **Verifiable derived claims (VDC)** | the gamer's input fingerprint (engagement / variety / tempo / steering / interaction) — each a pure property the *verifier re-derives*, so the producer cannot lie about it |
| 4 | **Selective disclosure (SD)** | the gamer commits to the whole claim set and reveals only a chosen subset (flat and Merkle) — membership + binding verified, hidden values absent |
| 5 | **ZK property proof** *(ceremony-gated)* | prove "value ≥ threshold" *without revealing the value* — scaffolded with an honest deferral: no fake proof ships before the trusted-setup ceremony (verifies as **DEFERRED**, never pass/fail) |
| 6 | **Two-engines flywheel** *(breadth-gated)* | the certified corpus feeds the anti-cheat — read-only, defers at today's N=1, writes no threshold |
| 7 | **Assertion plane (anti-cheat)** | the *same* session (M17) that is the certified-human data bundle is *also* a synchronized presence proof (PoSP) — schema + KAS commitment + verdict verified offline. **One match, two engines** (IoTeX: Poseidon `events_roots` + `isFullyEligible()`) |
| 8 | **Tri-plane fusion** | one match, **three planes federated under one `session_id`** — assertion + observation (cryptographic) + meaning (attested today; **earns** a cryptographic join the instant a PoSP carries the matching PoAC-chain root — F3); the **separation law is machine-checked** (observation/meaning never assert). One match *is* one IoTeX-anchored object across three organs (Poseidon + W3bstream/DA + ioID/consent) |

## Full cryptographic verification (optional tier)

The offline command proves the *logic*. To additionally check the **real Groth16 humanity proof, the
on-chain consent view-call, and the Poseidon matrix↔root binding**, run:

```bash
python scripts/verify_wmp_ladder.py --full     # needs Node + snarkjs + testnet RPC
# (snarkjs is vendored under contracts/node_modules; run `npm install` there if absent)
```

This reconstructs the snarkjs proof from the bundle's own bytes and verifies it against the published
verifying key, live-calls the IoTeX testnet consent registry, and recomputes the Poseidon root — the
same proof accepted on-chain. It reports **VERIFIED 5/5 zero-stub** (recency explicitly deferred on
this bundle — see below).

## Honest limits (carry with every claim)

- **N = 1** — one session, one player. This is a *demonstration of the lane*, not a dataset business.
- **IoTeX testnet**, not mainnet. **No buyer**, no transaction. **TGE frozen** — nothing is purchasable.
- **Action-channel only** — the observation channel (what the human saw) is absent by design; the
  anti-cheat's micro-signal biometric moat never exports.
- **Deferred rungs are externally gated**, never faked — rung 5 on a trusted-setup ceremony, rung 6 on
  corpus breadth. They activate the moment their gate opens.
- Recency on this bundle is honestly deferred (one anchored beacon near the session window, no clean
  open/close pair) — never claimed as beacon-bound.

## Where to look next

- The bundle: `wmp_corpus_real/wmp_corpus.jsonl` · the first-real-bundle report: `audits/wmp-phase2-first-real-bundle-2026-07-11.md`
- The verifier: `sdk/wmp_verify.py` (zero-trust; never imports bridge code) · the adversarial matrix: `docs/wmp-adversarial-matrix-2026-07-11.md`
- The ladder docs: `docs/wmp-derived-claim-vdc1-2026-07-11.md` · `docs/wmp-selective-disclosure-sd1-2026-07-11.md` · `docs/wmp-gated-loops-zkp1-fly1-2026-07-11.md`

---

*Everything here runs from the committed repository. Clone it, run the command, trust us for nothing.*
