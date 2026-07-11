# QorTroller — How a Pilot Actually Works (Plain-English Walkthrough)

*Companion to the one-page technical summary. This version is for reading before the first call —
no jargon, no crypto vocabulary, just what happens and why.*

---

## The problem you have

When your event runs online — especially cloud gaming or Remote Play — you can't install
anti-cheat on machines you don't control. So when someone accuses a player of botting,
account-sharing, or "someone else was playing for them," you have nothing but VOD review and
arguments. Disputes become unwinnable he-said-she-said.

**QorTroller gives you a receipt:** proof that a real physical controller was producing the
inputs, and that those inputs are what caused the kills on screen — sealed at match time,
checkable later by anyone, without trusting us.

Think of it as matching the **security-camera footage** (the screen) against the **door-badge
swipes** (the controller's actual trigger pulls) on a tamper-evident timeline. If a bot, a
replay, or a remote farm played the match, the swipes and the footage don't line up — and the
receipt says so.

---

## The steps, from your chair

**1. Agree the scope (one conversation).**
One game, one bracket night, opt-in players only. The signal is *review-only* — it can inform
your human judgment; it never auto-bans anyone. That limit is a feature, not a hedge: it is in
writing and we hold to it.

**2. Players opt in.**
Each participating player consents to the capture — and they own their data, with consent
categories they can revoke. For the pilot, realistically *we* run the capture rig for a handful
of showcase matches. You don't install anything.

**3. Matches run completely normally.**
The capture is passive — it watches the stream window and the controller cable. It doesn't
touch the game, doesn't need the publisher's permission, and doesn't add lag to the player's
console.

**4. After each match, the evidence self-seals.**
The moment capture stops, everything is locked with cryptographic fingerprints — nobody
(including us) can quietly edit it afterward. Within about fifteen minutes we produce the
result — *"these kills are bound to real trigger pulls on this session"* — plus a **match
certificate**: a small file that carries the verdict and the seals.

**5. You receive three things per match.**
The certificate, a one-line verdict, and a re-check command. The last one matters most: you —
or any third party, a co-organizer, a skeptical player, a journalist — can run **one command**
that re-verifies the whole thing, including the cryptographic proof and the public blockchain
timestamp. You never have to take our word for it.

**6. When a dispute happens** — *"that guy wasn't even playing"* —
you pull the certificate for that match. It either supports the accusation or it doesn't. It's
*one input* into your ruling, like a line judge's call: it informs, the referee decides.

**7. End of pilot.**
You have a stack of receipts and a real answer to "was this signal useful?" — which is all a
pilot should promise.

---

## Straight answer to "so it catches cheaters?"

This is where most tools oversell. We won't:

- ✅ It catches the **nobody's-actually-there** cheats: bots, replays, account farms, someone
  streaming inputs from another machine — precisely the class that is invisible to normal
  anti-cheat on cloud and Remote Play.
- ❌ It does **not** catch a real human using an aimbot (they are genuinely present), and it
  does not identify *which* human is playing. It is one layer, designed to stack with the
  review tools you already use.
- Today's grade: **advisory pilot on a test network** — a smoke detector, not a judge.

That honesty is the point. Every claim we make is written down with its limits, and the receipt
that backs it is something you can re-run yourself.

---

## What we bring vs. what we need from you

| We bring | You provide |
|---|---|
| The capture rig and operators for the pilot matches | A schedule and a title |
| A sealed certificate + verdict per match, usually within ~15 minutes | Opt-in players |
| The one-command re-check anyone can run | Agreement that the signal is review-only for the pilot window |
| Our claim limits, in writing | Your honest feedback on whether it helped |

**Cost to you: no software installs, no game modifications, no player-side downloads, nothing
purchasable — there is no token and nothing for sale in this pilot.**

---

*Technical companion (claims, limits, and the exact checks): the QorTroller pilot one-pager.
Questions and verification walkthroughs: we'll do them live on the first call.*
