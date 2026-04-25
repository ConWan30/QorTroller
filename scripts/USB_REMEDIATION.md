# USB Enumeration Remediation — How To Run

## What this fixes

DualSense Edge USB-C polling rate stuck at 80–118 Hz instead of the
expected ~1000 Hz.  The bridge's PCC layer (Phase 234.7) requires
≥950 Hz to classify as `NOMINAL`; without that, every grind session
fails-closed and `chain_length` cannot advance.

## What the script does

`scripts/usb_remediate.py` runs four software-only remediations in
order, restarting the bridge and measuring poll_rate_hz after each.
Stops at the first one that brings the rate ≥ 800 Hz.

| Step | What | Elevation |
|---|---|---|
| 1 | Disable USB Selective Suspend (current power scheme, AC + DC) | none |
| 2 | Disable Power Management on every DualSense Edge HID interface (per-device registry) | admin |
| 3 | Force USB re-enumeration via `Disable-PnpDevice` + `Enable-PnpDevice` cycle | admin |
| 4 | Disable Power Management on parent USB Root Hubs | admin |

Steps 2–4 self-elevate via UAC (`Start-Process -Verb RunAs`).  You'll
see Windows UAC prompts during the run — those are real and need a
human click.  If you want zero prompts, run the entire Claude Code
session from an already-elevated PowerShell.

## How to run

Two ways depending on how much autonomy you want Claude Code to have.

### Option A — Manually invoke once (you watch)

```powershell
cd C:\Users\Contr\vapi-pebble-prototype
python scripts/usb_remediate.py
```

The script writes the bridge log to
`scripts/_usb_remediate_bridge.log` while it iterates.  Each step
prints output inline and reports the measured `poll_rate_hz`.  Total
runtime ~5 minutes (4 steps × 30s warmup + measurement).

### Option B — Hands-off via Claude Code

Start a new Claude Code session with bypassed permissions, then ask
Claude to run the remediation.  The allow-list in
`.claude/settings.local.json` already permits:

- `Bash(python scripts/usb_remediate.py)`
- `Bash(powershell.exe:*)`, `powercfg:*`, `Get-PnpDevice:*`, etc.
- Reading the bridge log

```powershell
claude --permission-mode bypassPermissions
```

Then in the Claude session:

> Run `python scripts/usb_remediate.py` and report whether it reached
> 800 Hz.  If it didn't, summarize which steps were tried and what
> physical fixes are left.

Claude will execute the script, watch the output, and report back
without prompting on each Bash call.  UAC prompts for elevation still
appear — those can't be bypassed without running Claude itself in an
admin shell.

## Physical fixes the script CAN'T do

If all four software remediations exhaust without reaching the target,
these are the next moves (need your hands):

- Try a different USB-C **data-capable** cable (the PS5-included cable
  is data-capable; cheap chargers are not)
- Plug into a **chassis-direct** USB 3.0+ port, not a hub or dock
- **Power-cycle the controller** — hold the PS button ~10 seconds
  until the lightbar dies, wait 3s, plug back in

## Verification after remediation

If the script reports `>> SUCCESS`, the bridge is already running with
the new settings.  Confirm with:

```powershell
python check_grind.py
```

Look for:

```
capture_state          NOMINAL
host_state             EXCLUSIVE_USB
poll_rate_hz           ≥ 800
grind_ready            True
session_counting_paused  False
>> OPEN     gate is open ...
```

When you see that, real-grind config is ready.  Switch
`bridge/.env` to:

```
GRIND_SESSION_ID=grind_phase235_v1
GRIND_TARGET=100
```

Then restart bridge and start the 100-session run.

## What the script will NEVER do

- Modify `bridge/.env`'s `BRIDGE_PRIVATE_KEY`
- Push commits, send Slack/email, change CI
- Disable Windows Defender or any security software
- Install third-party drivers
- Touch any registry key outside USB / HID / Power policy paths

If you want to extend it, the `REMEDIATIONS` list in
`scripts/usb_remediate.py` is the only place to edit.
