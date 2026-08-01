# Retina Bridge Agent — Local Gameplay Digest Monitor

This is **not a Buzz agent**. It is a local, operator-fired Python daemon that runs alongside the QorTroller bridge and uses the Retina Visual Oracle to produce game-state digests from gameplay video/frames.

## What it is

- **Name:** `retina_bridge_agent.py`
- **Purpose:** Autonomously analyze gameplay frames when the bridge is up and emit a structured digest (no raw video, no frames, no HID, no keys).
- **Default model:** `nvidia/nemotron-nano-12b-v2-vl`
- **Primary corpus:** NCAA College Football 26
- **Output:** `audits/retina_bridge_agent/<session_id>.json` with visual-context digests and cross-modal verdicts.

## One-line rule

> The agent can **see** the gameplay in order to **verify** it, but it must **never repeat the pixels**. It only emits the digest.

## Activation

The agent is **operator-fired** and **fail-closed**. It only starts if:

1. `RETINA_BRIDGE_AGENT_ENABLED=1` is set.
2. The bridge `/health` endpoint is reachable.
3. A session is active (or a video/frames source is configured).

## Environment variables

```powershell
$env:RETINA_BRIDGE_AGENT_ENABLED = "1"
$env:BRIDGE_BASE_URL = "http://localhost:8080"
$env:RETINA_BRIDGE_AGENT_INTERVAL_S = "5"
$env:RETINA_FRAME_SOURCE = "video"          # game | video | dir
$env:RETINA_VIDEO_PATH = "C:\capture\session_01.mp4"
$env:RETINA_FRAME_DIR = ""
$env:NIM_API_KEY = "..."                     # required for VLM
$env:GAME_PROFILE_ID = "ncaa_cfb_26"         # or "ncaa_cfb_27", "cod_warzone", etc.
$env:RETINA_AGENT_AUDIT_DIR = "audits/retina_bridge_agent"
$env:RETINA_AGENT_STOP_FILE = "audits/retina_bridge_agent.STOP"
```

## Frame sources

| Source | Description | Use when |
|--------|-------------|----------|
| `video` | Analyze a local `.mp4` file frame-by-frame | You have a recorded session |
| `dir`   | Analyze a directory of `.png`/`.jpg` frames | You have extracted frames |
| `game`  | Use the live `RetinaGameCapture` window source | Bridge has WGC capture enabled (Windows only) |

## What the agent does

1. Polls bridge `/health` every `RETINA_BRIDGE_AGENT_INTERVAL_S`.
2. When bridge is up and session is active (or source is configured), it reads frames at the `VISUAL_ORACLE_SAMPLE_RATE` cadence.
3. Calls `VisualOracle.analyze_frame()` on each sampled frame.
4. Calls `VisualOracle.verify()` to cross-check visual context against optional motion/input features.
5. Appends each digest to a session JSONL.
6. When the session ends or the stop file appears, it closes the file and writes a summary JSON.

## Output format

Each line in the session JSONL is a `RetinaObservationDigest`:

```json
{
  "timestamp_ns": 1234567890123456789,
  "frame_number": 300,
  "frame_hash": "sha256:...",
  "game_state": "gameplay",
  "game_title": "NCAA Football 26",
  "confidence": 0.87,
  "screen_description": " Alabama leads 14-7, 2nd quarter, 3rd and 5 ",
  "football_home_score": 14,
  "football_away_score": 7,
  "football_quarter": 2,
  "football_down": 3,
  "football_yards_to_go": 5,
  "cross_modal_match": true,
  "cross_modal_anomaly": false,
  "cross_modal_confidence": 0.91,
  "model": "nvidia/nemotron-nano-12b-v2-vl"
}
```

The summary JSON contains aggregate stats:

```json
{
  "session_id": "...",
  "started_at_ns": 1234567890123456789,
  "ended_at_ns": 1234567899999999999,
  "frame_count": 1200,
  "observation_count": 40,
  "gameplay_ratio": 0.82,
  "anomaly_count": 2,
  "verdict": "SYNCHRONIZED_CONTROLLER | IDENTITY_ONLY | ...",
  "commitment_root": "0x..."
}
```

## Stopping the agent

Create the stop file:

```powershell
New-Item -ItemType File -Path "audits/retina_bridge_agent.STOP" -Force
```

Or run `python scripts/retina_bridge_agent.py --stop`.

## Rails

- **No raw frames in output.** The agent never writes image files, base64 frames, or pixel arrays to disk except the VLM's input (which is ephemeral and in-memory only).
- **No Buzz/Nostr posting.** This is a truth-plane agent; it writes to the local `audits/` directory.
- **No keys.** It does not sign or post anything.
- **No live capture arming.** It analyzes whatever frame source is already running; it does not start WGC/UVC capture itself.
- **Operator-fired only.** It exits immediately if `RETINA_BRIDGE_AGENT_ENABLED` is not `1`.

## Extending the agent

If you want the agent to push a digest to a channel, let the operator/EA bot read `audits/retina_bridge_agent/*.summary.json` and post a **pointer** (session_id, verdict, commitment_root) to `#matches`. The agent itself stays off the social plane.
