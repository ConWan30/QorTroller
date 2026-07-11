# WMP Selective Disclosure (SD-1) — 2026-07-11

**The rung.** VDC-1 made the gamer's certified data yield verifiable derived claims. SD-1 lets the
gamer choose **which** of those claims a consumer sees — committing immutably to the *whole* set,
then revealing only a subset, hiding the rest. Purest "Core Controllers of their Data": the gamer
decides what leaves their hands.

This is the **desk-buildable, no-ceremony half** of "ZK selective disclosure." The zero-knowledge
half (prove `value ≥ threshold` *without revealing it*) is the ceremony-gated rung above — named,
deferred, honest.

## What it is

`sdk/wmp_disclosure.py` (pure; imports only `sdk.wmp_derived`).

- **`build_disclosure(claims, reveal_ids=None)`** — commits to a set of VDC claims (all bound to one
  certified bundle) and reveals the chosen subset. The commitment is a hash over *bundle + count +
  sorted leaf hashes + sorted claim-type inventory* — so a discloser cannot cherry-pick post-hoc,
  hide the *existence* of claims, or misstate the inventory without breaking the root.
- **`verify_disclosure(disclosure)`** (fail-closed) — recomputes the commitment (immutability), and
  checks every revealed claim hashes to its `claim_hash`, binds to the disclosure's bundle, and is a
  member of the committed set + inventory.

## Honest ceiling

| proves | does NOT |
|---|---|
| revealed claims are members of an **immutable committed set** of N claims | re-derive revealed VALUES without the bundle (that's VDC-with-bundle) |
| all bound to **one certified bundle** | assert anything about **hidden claims' values** |
| **count + claim-type inventory** are committed (tamper-evident) | hide hidden claims' **hashes** (a Merkle-tree upgrade would) |
| the gamer selectively reveals **only chosen** claim values | provide **zero-knowledge** (the ceremony-gated property-proof rung) |

## Reproduce

```bash
pytest bridge/tests/test_wmp_disclosure_sd1.py -q   # 11 pinning tests
```

Example: commit to the 5-dim fingerprint of a session, reveal only *engagement* + *steering*, and a
consumer confirms — with zero trust — that those two are genuine members of a committed 5-claim set
bound to a certified-human bundle, while *variety*, *tempo*, and *interaction* stay hidden (values
absent; only their hashes are in the envelope; even `reveal_ids=[]` proves the set exists).

## Rails (test-pinned)

tamper the root → FAIL · tamper set_size → FAIL · misstate the inventory → root FAIL · lie about a
revealed value → membership FAIL · smuggle a foreign (uncommitted) claim into `revealed` → membership
FAIL · claims from two bundles → refused at build.

## Ladder position

certified data (WMP) → verifiable derived claim (VDC-1) → **selective disclosure (SD-1, here)** →
ZK property proof (ceremony-gated) → corpus-scale analytics (breadth-gated / post-card).

---

*WMP SD-1 — opened 2026-07-11 (C1: commit-and-selective-reveal over VDC claims). Living doc. Next
(ceremony-gated): ZK property proof — prove a claim's value satisfies a predicate without revealing it.*
