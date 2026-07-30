# Buzz Phase 1 — Operator Setup Runbook

Companion to `docs/design/buzz-qortroller-gamer-mvp-v0.md`.
Decision recorded: **owner-attested (NIP-OA)** bot auth.

Everything here is verified against the vendored `buzz/` tree on this machine
unless explicitly marked NOT YET RUN.

---

## 0. Key-safety discipline (read once, applies to every step)

- **You run every key-generating command yourself.** Never paste a secret key,
  `nsec`, or auth tag into a chat window, an issue, a commit, or a PR — including
  to an AI agent. An agent that sees a key means the key is burned.
- The old `ea_buzz_bridge.py` scratch files contained a hardcoded `nsec`. They are
  scrubbed, but **that key is compromised — do not reuse it.**
- Secrets live only in a local `.env` that is gitignored.
- The NIP-OA **auth tag is a capability credential**, not a public value. Treat it
  like a bearer token.

---

## 1. Environment findings (already verified on this machine)

| Check | Result |
|---|---|
| `cargo --version` | 1.97.1 ✅ |
| `docker --version` | 29.3.1 ✅ |
| `node --version` | v24.13.0 ✅ |
| Default Rust host | `x86_64-pc-windows-gnu` ⚠️ **cannot link** (`dlltool.exe` not found) |
| MSVC Build Tools | Installed (VS Build Tools 2022 + VS 18 Insiders MSVC) ✅ |
| Fix applied | `rustup toolchain install stable-x86_64-pc-windows-msvc` ✅ |
| Python Nostr signing | ❌ no `coincurve` / `secp256k1` / `nostr_sdk`; only `ecdsa` (**wrong algorithm** — Nostr needs BIP-340 Schnorr) |

### 1.1 The Rust toolchain rule for this repo

`buzz/rust-toolchain.toml` pins channel `1.95.0`, which resolves to the **gnu**
host and fails to link. Always build Buzz Rust targets with the MSVC toolchain
override:

```powershell
cargo +stable-x86_64-pc-windows-msvc build -p <crate>
```

This is required for `buzz-admin` (your key generation) too — not just the helper.

---

## 2. Why there is a small Rust helper (architecture decision)

Two V-check findings forced this, and they are worth understanding because they
kill the "just do it in Python over a WebSocket" plan:

1. **`buzz messages send` has no custom-tag flag.** Its options are `--channel`,
   `--content`, `--kind`, `--reply-to`, `--broadcast`, `--file`. So the CLI alone
   **cannot** emit the queryable digest tags the design requires (`session_id`,
   `verdict`, `commitment_root`, `poep_enabled`, …). Without tags, third parties
   cannot filter/audit by session — which is the whole point.
2. **Python here cannot sign Nostr events correctly.** No BIP-340 Schnorr library
   is installed. The `ecdsa` package is ECDSA, not Schnorr. The original draft
   bridge also hashed `sort_keys` JSON, but NIP-01 requires
   `sha256([0, pubkey, created_at, kind, tags, content])`. Both bugs would produce
   events the relay rejects.

**Resulting split (Architecture C):**

```
Python (QorTroller truth plane)          Rust (bytes on the wire)
  HardwareWatcher / sessions.db   ──►    qortroller-buzz publish
  computes the digest JSON               signs kind 9 + custom tags
  never touches crypto                  NIP-42 + NIP-OA via buzz-ws-client
```

Python owns what it is good at. Signing stays on the already-tested
`buzz-sdk` / `buzz-ws-client` path.

---

## 3. The helper: `qortroller-buzz` (built and smoke-tested ✅)

Location: `buzz/examples/qortroller-buzz/` (follows the sanctioned
`examples/countdown-bot` pattern; added to the workspace members list).

```powershell
cd buzz
cargo +stable-x86_64-pc-windows-msvc build -p qortroller-buzz
# binary: buzz\target\debug\qortroller-buzz.exe
```

### Subcommands

| Command | Purpose | Reads | Prints |
|---|---|---|---|
| `whoami` | derive the bot pubkey | `BUZZ_PRIVATE_KEY` | **public** key only |
| `authtag` | compute the NIP-OA attestation | `BUZZ_OWNER_PRIVATE_KEY` (+ bot pubkey) | the auth tag JSON |
| `publish` | publish one digest as kind 9 with tags | stdin JSON, `BUZZ_PRIVATE_KEY`, `BUZZ_AUTH_TAG`, `BUZZ_RELAY_URL` | `{event_id, accepted, message}` |

### Verified safety rails (smoke-tested)

| Rail | Test result |
|---|---|
| Missing `BUZZ_PRIVATE_KEY` → clear refusal | ✅ |
| `whoami` correctness | ✅ privkey=1 → `79be667e…` (secp256k1 generator) |
| Self-attestation rejected | ✅ "owner and agent pubkeys must differ" |
| `nsec` anywhere in content → refuse | ✅ |
| Bare 64-hex tag value → refuse | ✅ (guards against pasting a key as a tag) |
| `commitment_root` 64-hex → allowed | ✅ (passes guard, proceeds to relay) |
| Content cap 8 KiB | ✅ enforced before any network call |
| Caller-supplied `h` tag → refuse | ✅ (`h` is derived from `channel`) |

---

## 4. Step-by-step setup

### Step 1 — Start the relay

```powershell
cd C:\Users\Contr\vapi-pebble-prototype\buzz
docker compose up -d          # Postgres + Redis + Typesense
cp .env.example .env          # if you have not already
```

Then run the relay. Note the correct URL is **`ws://localhost:3000`**, not 8080
(8080 was wrong in the original draft).

For owner-attested bot auth, the relay needs these set (in `buzz/.env`):

```ini
BUZZ_REQUIRE_RELAY_MEMBERSHIP=true
BUZZ_ALLOW_NIP_OA_AUTH=true
RELAY_OWNER_PUBKEY=<your operator pubkey hex>
BUZZ_RELAY_PRIVATE_KEY=<relay signing key hex>
RELAY_URL=ws://localhost:3000
```

`BUZZ_ALLOW_NIP_OA_AUTH=true` is what lets an owner-attested, non-member bot key
connect. Without it, the bot is rejected even with a valid tag.

**Verify:** the relay logs a successful start and `curl http://localhost:3000`
returns NIP-11 metadata.

### Step 2 — Generate the EA bot key (YOU run this; I never see it)

```powershell
cd C:\Users\Contr\vapi-pebble-prototype\buzz
cargo +stable-x86_64-pc-windows-msvc run -p buzz-admin -- generate-key
```

Output shape:

```
Public key:  <64 hex>
Secret key:  <64 hex>
```

- Put the **secret** in your local `.env` as `BUZZ_PRIVATE_KEY`. It is not
  recoverable — save it immediately.
- Keep the **public** key handy; you will need it in Step 4.
- **This key must NOT be derived from ioID tokenId 498.** The gamer identity
  proves the human; the EA bot key proves the operator steward. Keeping them
  separate is what preserves the sovereignty claim (design doc §2).

### Step 3 — Confirm your operator npub is a relay member

The NIP-OA path works because *the owner* is already an allowed relay identity.

```powershell
cargo +stable-x86_64-pc-windows-msvc run -p buzz-admin -- list-members
```

If your operator pubkey is not listed:

```powershell
$env:BUZZ_RELAY_PRIVATE_KEY="<relay signing key>"
cargo +stable-x86_64-pc-windows-msvc run -p buzz-admin -- add-member --pubkey <operator pubkey hex>
```

### Step 4 — Mint the NIP-OA auth tag (YOU run this; done ONCE, offline)

```powershell
cd C:\Users\Contr\vapi-pebble-prototype\buzz
$env:BUZZ_OWNER_PRIVATE_KEY="<your operator secret>"
$env:BUZZ_PRIVATE_KEY="<the bot secret from Step 2>"
.\target\debug\qortroller-buzz.exe authtag
```

It prints a tag of the form:

```
["auth","<owner_pubkey>","<conditions>","<schnorr_sig>"]
```

Save that whole JSON string as **`BUZZ_AUTH_TAG`** in your `.env`, then
**unset `BUZZ_OWNER_PRIVATE_KEY`**. This is the important part: the bot then
runs holding only its own key plus a scoped capability. If the bot host is ever
compromised, your operator key is not.

Optional scoping (recommended once you know your shape):

```powershell
.\target\debug\qortroller-buzz.exe authtag --conditions "kind=9"
```

### Step 5 — Create the channels

In the Buzz desktop app, create and copy the UUIDs for:

| Channel | EA bot member? |
|---|---|
| `#lobby` | no |
| `#rig-ops` | **yes** |
| `#matches` | **yes** (postcards only) |
| `#disputes` | no (Phase 3) |
| `#announcements` | no |

The EA bot is a `Bot`-role member, never an admin.

### Step 6 — Fill in the bot env

Copy `scripts/qortroller_buzz_bot.env.example` to a local, gitignored `.env`:

```ini
BUZZ_PRIVATE_KEY=<bot secret from Step 2>
BUZZ_AUTH_TAG=["auth","...","","..."]     # from Step 4
BUZZ_RELAY_URL=ws://localhost:3000
BUZZ_CHANNEL_IDS=<rig-ops-uuid>,<matches-uuid>
BRIDGE_BASE_URL=http://localhost:8000
QORTROLLER_DEVICE_ID=581a836c
QORTROLLER_IOID_TOKEN=498
# BUZZ_OWNER_PRIVATE_KEY intentionally NOT set — used once in Step 4 only
```

### Step 7 — First real publish (end-to-end proof)

```powershell
cd C:\Users\Contr\vapi-pebble-prototype\buzz
'{"channel":"<rig-ops-uuid>","content":"QorTroller EA online","tags":[["qortroller","1"],["rig_state","UNKNOWN"],["poep_enabled","false"],["l6b_enabled","false"]]}' | .\target\debug\qortroller-buzz.exe publish
```

Expected: `{"event_id":"…","accepted":true,"message":""}` and the message
appears in `#rig-ops` in the desktop app.

**This is the Phase 1 acceptance gate.** If this works, the interop path is real.

Note the honesty tags: `rig_state=UNKNOWN`, `poep_enabled=false`,
`l6b_enabled=false`. Publish what is true, including "we don't know yet."

---

## 5. What is still NOT built (honest status)

| Piece | Status |
|---|---|
| `qortroller-buzz` helper (sign + publish + authtag) | ✅ built, smoke-tested |
| Relay running with NIP-OA enabled | ⬜ Step 1 (you) |
| EA bot key | ⬜ Step 2 (you) |
| Auth tag | ⬜ Step 4 (you) |
| Channels + UUIDs | ⬜ Step 5 (you) |
| First live publish | ⬜ Step 7 (acceptance gate) |
| `scripts/qortroller_buzz_bot.py` real state reads | ⬜ scaffold only — `_read_rig_state` returns `UNKNOWN`, `_read_session_postcard` returns `None`. Wiring these to `HardwareWatcher` / `sessions.db` is the next build step. |
| Command loop (`!status`, `!ready`, `!session`) | ⬜ needs a read path (`buzz messages get` polling, or a Rust subscribe loop) |
| kind 0 profile + kind 9000 self-add | ⬜ not yet in the helper (countdown-bot shows the exact shape) |
| ACP conversational EA | ⬜ Phase 4, deliberately deferred |

**Nothing above claims presence, humanity, or anti-cheat.** Phase 1 only proves
that a QorTroller-signed, tagged, owner-attested digest can reach a Buzz channel.

---

## 6. Failure modes and what they mean

| Symptom | Cause | Fix |
|---|---|---|
| `error calling dlltool 'dlltool.exe'` | gnu Rust host, no MinGW | use `cargo +stable-x86_64-pc-windows-msvc` |
| `auth-required: verification failed` | closed relay, no/stale attestation | check `BUZZ_ALLOW_NIP_OA_AUTH=true`, re-mint `BUZZ_AUTH_TAG` |
| `BUZZ_AUTH_TAG is not a valid attestation for BUZZ_PRIVATE_KEY` | tag was minted for a different bot key | re-run Step 4 with the correct bot key |
| `owner and agent pubkeys must differ` | you attested the bot to itself | owner key ≠ bot key |
| `os error 10061` on publish | relay not running | Step 1 |
| Bot connects but cannot post to a channel | not a channel member | add the bot pubkey to the channel, or self-add kind 9000 in an open channel |
| `tag '…' looks like a bare 64-char hex key` | a key almost leaked into a tag | intended guard — rename to `commitment_root` if it is genuinely a commitment |

---

## 7. Recurring hygiene

Before any commit that touches this lane:

```powershell
git grep -n "nsec1"                        # must return nothing
python scripts\vapi_invariant_gate.py      # must stay 184
python -m py_compile scripts\qortroller_buzz_bot.py
```
