---
name: a2a-relay
description: The agent-to-agent terminal bus (scripts/a2a_pkg_relay.py) for collaborating with grok or another Claude session via sealed hash-bound envelopes instead of operator copy-paste. Read before posting, delivering, or claiming an A2A round.
---

# A2A terminal bus

`scripts/a2a_pkg_relay.py` moves *messages* between agent CLIs as sealed,
hash-bound envelopes under `docs/a2a/pkg/mailbox/`. It never commits anything.
Schema `qortroller-a2a-envelope-v1`; `envelope_id` is a SHA-256 of the canonical
envelope, `body_sha256` pins the round file's exact bytes.

## The loop

```bash
export PYTHONIOENCODING=utf-8          # REQUIRED — see gotchas

python scripts/a2a_pkg_relay.py post \
    --from claude --to grok \
    --round  docs/a2a/<arc>/round-NN-claude-<kind>.md \
    --prior  docs/a2a/<arc>/round-NN-1-grok-<kind>.md \
    --expect docs/a2a/<arc>/round-NN+1-grok-<kind>.md \
    --subject "..." --mandate "..."

python scripts/a2a_pkg_relay.py deliver --envelope <id> --handoff
python scripts/a2a_pkg_relay.py pending --for grok
python scripts/a2a_pkg_relay.py claim   --for grok      # live peer session acts
python scripts/a2a_pkg_relay.py ack     --envelope <id> # reply landed
```

Round files live in the arc's own directory (`docs/a2a/<arc>/`), not in the
mailbox. The mailbox is shared, topic-agnostic plumbing.

## Gotchas that cost real time

**`PYTHONIOENCODING=utf-8` is required.** The script prints `→` and Windows'
default cp1252 console codec raises `UnicodeEncodeError` mid-command. It fails
*after* doing work, so state can be half-written.

**`--handoff` is the working path; headless `--fire grok` largely isn't.** The
fire path passes `--prompt-file`, which grok documents as *single-turn*
("prints the response and exits"). A single turn cannot read the code,
investigate, and write a reply file — it produces a one-line stub. This is an
architecture mismatch, not a permission problem: raising the permission mode
does not fix it. Use `--handoff` and let a live multi-turn peer session claim it.

**Claim by explicit `envelope_id`, not FIFO.** The mailbox carries ~39 pending
envelopes across many old arcs. A bare `claim --for grok` can surface a stale
one from a different topic. Paste the id.

**Round files are untracked until the operator commits them.** `git stash -u`
will swallow a peer's freshly-written reply. Recover with
`git checkout stash@{0}^3 -- <path>` (untracked files live in the stash's third
parent). Check for agent-written files before stashing.

**Post from the tree both agents will claim from.** Envelopes reference repo-relative
paths; a handoff written in one worktree while the peer works in another produces
"prior file missing" and hash confusion.

## Rails (they apply to both sides)

- **Single committer.** Agents stage; the operator commits and pushes. Neither
  agent commits, pushes, or seals autonomously.
- **Cross-verified building.** Either agent may build, but staged work is
  accepted only after the *other* independently verifies it (tests, PV-CI,
  rails) and records that verification in its round. Role purity is not the
  rail; cross-verification is.
- **Verdict tags:** `BUILD-NOW` / `GATED:<gate>` / `REFUTED:<why>`.
- **`claim ⊆ reality`.** Report what you verified. Never round a verdict up.

When you disagree with a peer's disposition, say so explicitly and ask for the
cross-verify rather than quietly doing it your way — that is what the rail is for.

## Round shape

Design/proposal rounds: `## proposals` with `{id · design · rationale · why-novel}`.
Audit/build rounds: `## verdicts` with `{id · tag · evidence · build-result}`,
plus `## build-results` and `## open-questions`.

## Related

- `docs/a2a/pkg/qortroller-pilot-kit-a2a-loop.md` — the charter (roles, phasing)
- `docs/a2a/<arc>/` — per-arc round history; `docs/a2a/pkg/mailbox/ledger.jsonl` — event log
- `verification-first` skill — the standard a cross-verify is held to
