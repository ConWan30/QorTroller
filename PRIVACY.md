# Privacy & Data Policy

QorTroller is a public protocol repository. The **code** is world-readable. The **gamer's live data** is not.

## What stays off GitHub

These paths are gitignored and must never be committed:

- `.env`, `bridge/.env`, `scripts/*.env`, `agents/*.env`
- Wallet private keys, GitHub PATs, Buzz `nsec` values
- `sessions/` biometric captures and raw HID/IMU dumps
- Live JSONL match logs and operator audit dumps that contain raw frames or controller traces

Templates such as `scripts/qortroller_buzz_bot.env.example` are safe to commit because they contain empty placeholders only.

## What a clone can do without sharing data

- Read the protocol, contracts, and docs.
- Run `python scripts/vapi_invariant_gate.py`.
- Run `python scripts/verify_wmp_ladder.py` against the **published** stranger-verifiable bundle.
- Open Discussions and issues.

None of those steps upload your controller stream, webcam, or keys.

## What can leave your machine (opt-in)

| Feature | Data | How it is enabled |
|---------|------|-------------------|
| IoTeX chain writes | Public tx hashes / contract calls | Operator-fired, estimate-first, never automatic |
| Buzz digest posts | `session_id`, verdict, commitment root, honesty flags | Env-only keys; digest-only; no raw HID/frames |
| World-model export | Post-φ action channel only | Gamer wallet `msg.sender` consent on-chain |
| Live capture | Frames / HID stay local unless you export | Capture-rig operator path |

## What we do not do

- Commit secrets so the project "just works" for strangers. Strangers use the public verify path.
- Grant or revoke gamer consent from the bridge. Solidity requires `msg.sender == gamer`.
- Post raw HID, IMU, L4 features, full PoAC payloads, or keys to Buzz, Discussions, or Pages.

## Questions

Open a Discussion, or use the private contact in `SECURITY.md`.
