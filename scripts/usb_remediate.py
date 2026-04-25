"""USB enumeration remediation orchestrator.

Iterates through software-only fixes for the DualSense Edge HID polling
rate problem.  After each fix: restart the bridge, wait for warmup, query
/operator/bridge/capture-health, check poll_rate_hz.  Stop when poll rate
≥ TARGET_POLL_HZ or all remediations exhausted.

Usage (run from repo root, ideally with `claude --permission-mode
bypassPermissions` so each subprocess auto-approves):

    python scripts/usb_remediate.py

Some steps require admin elevation.  When elevation is required, the
script attempts a UAC self-elevate via `Start-Process -Verb RunAs`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT      = Path(__file__).resolve().parents[1]
BRIDGE         = "http://127.0.0.1:8080"
KEY            = "vapi-dev-local"
TARGET_POLL_HZ = 800.0           # NOMINAL is 950, 800 gives margin for jitter
WARMUP_S       = 30              # bridge startup + first PCC samples
POLL_TIMEOUT   = 5

DUALSENSE_VID = "054C"
DUALSENSE_PID = "0DF2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_ps(script: str, *, elevated: bool = False, capture: bool = True) -> tuple[int, str]:
    """Run a PowerShell snippet and return (exit_code, stdout+stderr)."""
    cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
    if elevated:
        # UAC self-elevation via Start-Process -Verb RunAs.  Output isn't
        # captured because the elevated process runs in a separate window.
        wrapped = (
            "Start-Process powershell.exe -Verb RunAs -Wait -ArgumentList "
            f"'-NoProfile','-NonInteractive','-Command',\"& {{ {script} }}\""
        )
        cmd.append(wrapped)
    else:
        cmd.append(script)
    try:
        r = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=120,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out
    except subprocess.TimeoutExpired as exc:
        return 124, f"timeout: {exc}"


def kill_bridge() -> None:
    """Kill any process listening on port 8080."""
    code, out = run_ps(
        "Get-NetTCPConnection -LocalPort 8080 -State Listen "
        "-ErrorAction SilentlyContinue | "
        "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
    )
    time.sleep(2)


def start_bridge() -> subprocess.Popen:
    """Start the bridge as a detached background process."""
    log_path = REPO_ROOT / "scripts" / "_usb_remediate_bridge.log"
    log_fh = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "bridge.vapi_bridge.main"],
        cwd=str(REPO_ROOT),
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    return proc


def get_poll_rate() -> float | None:
    """Hit the operator endpoint, return poll_rate_hz or None on failure."""
    req = urllib.request.Request(
        BRIDGE + "/operator/bridge/capture-health",
        headers={"x-api-key": KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=POLL_TIMEOUT) as r:
            d = json.loads(r.read())
            return float(d.get("poll_rate_hz", 0.0))
    except Exception:
        return None


def measure(label: str) -> float:
    """Restart bridge, wait for warmup, measure poll rate."""
    print(f"\n--- MEASURE: {label} ---")
    kill_bridge()
    proc = start_bridge()
    print(f"  bridge started (pid={proc.pid}); waiting {WARMUP_S}s for warmup")
    time.sleep(WARMUP_S)

    # Average 5 polls 2s apart for stability
    rates = []
    for i in range(5):
        r = get_poll_rate()
        if r is not None:
            rates.append(r)
        time.sleep(2)
    if not rates:
        print("  poll_rate: UNREACHABLE")
        return 0.0

    avg = sum(rates) / len(rates)
    print(f"  poll_rate samples: {[f'{r:.1f}' for r in rates]}  avg={avg:.1f} Hz")
    return avg


# ---------------------------------------------------------------------------
# Remediations (least to most invasive)
# ---------------------------------------------------------------------------

REMEDIATIONS: list[dict] = [
    {
        "name": "1. Disable USB Selective Suspend (current power scheme, AC + DC)",
        "elevated": False,  # current-scheme edits don't require admin
        "ps": (
            "powercfg /setacvalueindex SCHEME_CURRENT "
            "2a737441-1930-4402-8d77-b2bebba308a3 "
            "48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0; "
            "powercfg /setdcvalueindex SCHEME_CURRENT "
            "2a737441-1930-4402-8d77-b2bebba308a3 "
            "48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0; "
            "powercfg /setactive SCHEME_CURRENT; "
            "Write-Host 'USB Selective Suspend disabled'"
        ),
    },
    {
        "name": "2. Disable Power Management on every DualSense Edge HID interface",
        "elevated": True,  # HKLM writes need admin
        "ps": (
            f"$devs = Get-PnpDevice -PresentOnly | Where-Object {{ "
            f"$_.HardwareID -match 'VID_{DUALSENSE_VID}.PID_{DUALSENSE_PID}' "
            f"}}; "
            "foreach ($d in $devs) { "
            "  $key = \"HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\$($d.InstanceId)\\Device Parameters\"; "
            "  if (Test-Path $key) { "
            "    Set-ItemProperty -Path $key -Name 'EnhancedPowerManagementEnabled' -Value 0 -Type DWord -ErrorAction SilentlyContinue; "
            "    Set-ItemProperty -Path $key -Name 'SelectiveSuspendEnabled' -Value 0 -Type DWord -ErrorAction SilentlyContinue; "
            "    Write-Host \"  cleared power-mgmt on $($d.InstanceId)\"; "
            "  } "
            "}"
        ),
    },
    {
        "name": "3. Force USB re-enumeration (Disable + Enable PnP device)",
        "elevated": True,
        "ps": (
            f"$devs = Get-PnpDevice -PresentOnly | Where-Object {{ "
            f"$_.HardwareID -match 'VID_{DUALSENSE_VID}.PID_{DUALSENSE_PID}' "
            f"}}; "
            "foreach ($d in $devs) { "
            "  Disable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue; "
            "} "
            "Start-Sleep -Seconds 2; "
            "foreach ($d in $devs) { "
            "  Enable-PnpDevice -InstanceId $d.InstanceId -Confirm:$false -ErrorAction SilentlyContinue; "
            "} "
            "Write-Host 'PnP cycle complete'"
        ),
    },
    {
        "name": "4. Disable Power Management on parent USB Root Hub",
        "elevated": True,
        "ps": (
            "$hubs = Get-PnpDevice -PresentOnly -Class USB | Where-Object { "
            "  $_.FriendlyName -match 'Root Hub' -or $_.FriendlyName -match 'USB Hub' "
            "}; "
            "foreach ($h in $hubs) { "
            "  $key = \"HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\$($h.InstanceId)\\Device Parameters\"; "
            "  if (Test-Path $key) { "
            "    Set-ItemProperty -Path $key -Name 'EnhancedPowerManagementEnabled' -Value 0 -Type DWord -ErrorAction SilentlyContinue; "
            "    Set-ItemProperty -Path $key -Name 'AllowIdleIrpInD3' -Value 0 -Type DWord -ErrorAction SilentlyContinue; "
            "    Write-Host \"  cleared root-hub power-mgmt on $($h.InstanceId)\"; "
            "  } "
            "}"
        ),
    },
]


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 64)
    print("USB ENUMERATION REMEDIATION")
    print(f"Target: poll_rate_hz >= {TARGET_POLL_HZ}")
    print("=" * 64)

    # Baseline
    baseline = measure("BASELINE (no fixes applied)")
    if baseline >= TARGET_POLL_HZ:
        print(f"\n>> ALREADY GOOD: baseline {baseline:.1f} Hz >= {TARGET_POLL_HZ}")
        kill_bridge()
        return 0

    print(f"\n  baseline {baseline:.1f} Hz < {TARGET_POLL_HZ}; trying remediations")

    for step in REMEDIATIONS:
        print(f"\n========== APPLY: {step['name']} ==========")
        print(f"  elevated: {step['elevated']}")
        rc, out = run_ps(step["ps"], elevated=step["elevated"])
        if rc != 0:
            print(f"  PowerShell exit={rc} (continuing anyway)")
        if out:
            print(f"  output: {out.strip()[:400]}")

        rate = measure(f"after step '{step['name']}'")
        if rate >= TARGET_POLL_HZ:
            print(f"\n>> SUCCESS: poll_rate {rate:.1f} Hz >= {TARGET_POLL_HZ}")
            print(f">> Remediation that worked: {step['name']}")
            kill_bridge()
            return 0

    print(f"\n>> EXHAUSTED: no software remediation reached {TARGET_POLL_HZ} Hz")
    print(">> Physical fixes left to try (cannot be automated):")
    print("     - Different USB-C data cable")
    print("     - Different USB port (chassis-direct, USB 3.0+)")
    print("     - Power-cycle the controller (hold PS button 10s)")
    kill_bridge()
    return 1


if __name__ == "__main__":
    sys.exit(main())
