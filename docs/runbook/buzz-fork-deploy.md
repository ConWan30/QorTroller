# Buzz Fork Deployment — QorTroller Relay

## Overview

The forked Buzz relay (`ConWan30/buzz`, branch `qortroller/main`) adds
relay-side postcard validation for `#matches` channels. This document
covers deploying the fork to replace the vanilla relay at
`wss://qortroller.communities.buzz.xyz`.

## What the fork changes

1. **`validate_qortroller_postcard`** in `crates/buzz-relay/src/handlers/ingest.rs`
   - Rejects kind 9 messages in channels named "matches" that lack the
     required postcard tag set: `qortroller`, `session_id`, `verdict`,
     `poep_enabled`, `l6b_enabled`, `candidate_ok`
   - 4 unit tests pass: `cargo test -p buzz-relay qortroller`

2. **`publish-profile` subcommand** in `examples/qortroller-buzz/src/main.rs`
   - Publishes kind 0 (NIP-01 Metadata) with custom tags
   - Used by the gamer ioID claim flow

3. **Extended 64-hex allowlist** — `claim_pubkey` and `bot_pubkey` are
   public keys, not secrets

## Build

```powershell
# Debug (fast, for testing)
$env:CARGO_TARGET_DIR="D:\cargo-target"
cargo +stable-x86_64-pc-windows-msvc build -p buzz-relay

# Release (for production)
$env:CARGO_TARGET_DIR="D:\cargo-target"
cargo +stable-x86_64-pc-windows-msvc build --release -p buzz-relay
```

Binary: `D:\cargo-target\release\buzz-relay.exe`

## Deploy

The relay requires PostgreSQL 17 + Redis. The existing deployment at
`qortroller.communities.buzz.xyz` already runs these.

### Steps

1. **Build the release binary** (above)

2. **Stop the vanilla relay** on the server:
   ```bash
   # On the relay host
   systemctl stop buzz-relay  # or docker stop buzz-relay
   ```

3. **Replace the binary**:
   ```bash
   # Copy the forked binary to the server
   scp D:\cargo-target\release\buzz-relay.exe server:/opt/buzz/buzz-relay.exe
   ```

4. **Start the forked relay**:
   ```bash
   systemctl start buzz-relay  # or docker start buzz-relay
   ```

5. **Verify**:
   ```bash
   # Health check
   curl https://qortroller.communities.buzz.xyz/health

   # Post a non-postcard message to #matches — should be REJECTED
   buzz messages send --channel 0767a3ad-0a7c-4c7c-b195-fda9fe5ff7f7 \
     --content "test without tags"
   # Expected: error: invalid: channel 'matches' requires a QorTroller
   # session postcard with tag 'qortroller'

   # Post a valid postcard — should be ACCEPTED
   # (use the bot's publish helper)
   ```

## Rollback

If the forked relay has issues:

1. Stop the forked relay
2. Replace the binary with the vanilla `buzz-relay` from `block/buzz`
3. Start the relay

The database schema is unchanged — no migration needed for rollback.

## Tracking upstream

```bash
cd buzz
git fetch upstream
git rebase upstream/main qortroller/main
# Resolve conflicts in ingest.rs (the validation function)
git push origin qortroller/main --force-with-lease
```

The QorTroller-specific changes are isolated to:
- `crates/buzz-relay/src/handlers/ingest.rs` (validation function + call site + tests)
- `examples/qortroller-buzz/` (helper binary)
- `Cargo.toml` (workspace registration)

Rebasing should be straightforward unless upstream changes the
validation call site area in `ingest_event_inner`.
