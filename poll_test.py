"""Quick standalone DualSense Edge poll-rate test.

Measures the raw HID polling rate by reading directly from interface 3
of the controller via hidapi — bypasses the bridge entirely.  Use this
to test cable + port combinations rapidly without restarting the bridge.

Usage:
    python poll_test.py            # default 5-second window
    python poll_test.py 10         # custom window length

Requirements:
    - hidapi (already a bridge dependency: `pip install hidapi`)
    - The bridge must NOT be running (it holds the HID interface open).
      Stop it with Ctrl+C before running this.

Exit codes:
    0  PASS  rate >= 800 Hz (USB high-speed HID)
    1  FAIL  rate <  800 Hz (cable / port / driver issue)
    2  ERROR controller not found, hidapi missing, etc.
"""
from __future__ import annotations

import sys
import time

DUALSENSE_VID = 0x054C
DUALSENSE_PID = 0x0DF2   # CFI-ZCP1 (DualSense Edge)
TARGET_HZ     = 800.0
DEFAULT_WINDOW_S = 5.0

try:
    import hid
except ImportError:
    print("hidapi not installed.  Run: pip install hidapi")
    sys.exit(2)


def find_dualsense_interface() -> dict | None:
    """Find the DualSense Edge HID device.  Prefer interface 3 (high-speed,
    vendor-specific) but fall back to whatever USB interface is available."""
    candidates = list(hid.enumerate(DUALSENSE_VID, DUALSENSE_PID))
    if not candidates:
        return None
    # Prefer interface 3 if available (Phase 9 baseline per CLAUDE.md)
    for d in candidates:
        if d.get("interface_number") == 3:
            return d
    # Otherwise return the first one (interface 0 = generic gamepad)
    return candidates[0]


def main() -> int:
    window_s = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_WINDOW_S

    target = find_dualsense_interface()
    if target is None:
        print(f"DualSense Edge (VID=0x{DUALSENSE_VID:04X} PID=0x{DUALSENSE_PID:04X}) not found.")
        print("Plug the controller in via USB-C and re-run.")
        return 2

    iface = target.get("interface_number")
    print(f"Found {target.get('product_string', 'DualSense Edge')} interface {iface}")
    if iface != 3:
        print(f"  (interface 3 not exposed — falling back to interface {iface}; "
              f"rate may be lower than the high-speed channel)")

    try:
        dev = hid.device()
        dev.open_path(target["path"])
        dev.set_nonblocking(False)
    except Exception as exc:
        print(f"Could not open HID device: {exc}")
        print("If the bridge is running, stop it (Ctrl+C) — it holds the interface open.")
        return 2

    print(f"Sampling for {window_s:.1f}s...  (move the sticks / press buttons for best read)")
    count = 0
    start = time.monotonic()
    try:
        while time.monotonic() - start < window_s:
            data = dev.read(128, timeout_ms=100)
            if data:
                count += 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        dev.close()

    elapsed = time.monotonic() - start
    rate = count / elapsed if elapsed > 0 else 0.0

    print()
    print("=" * 56)
    print(f"  {count} reports in {elapsed:.2f}s")
    print(f"  Effective polling rate: {rate:.1f} Hz")
    print("=" * 56)
    print()

    if rate >= TARGET_HZ:
        print(f">> PASS  rate {rate:.0f} Hz >= {TARGET_HZ:.0f}  — USB high-speed HID active.")
        print("   Bridge will reach NOMINAL under default thresholds.")
        return 0

    if rate >= 200:
        print(f">> THROTTLED  rate {rate:.0f} Hz, USB low-speed HID mode.")
        print("   Likely cable is data-capable but pipe is negotiating low-speed.")
        print("   Try a different USB port (chassis-direct, USB 3.0+).")
        return 1

    if rate >= 50:
        print(f">> POWER-ONLY OR DEFAULT HID  rate {rate:.0f} Hz.")
        print("   Cable is most likely power-only (no D+/D-) or USB enumeration")
        print("   is stuck in standard 8ms HID mode (~125 Hz).  Try a known-good")
        print("   data cable — the cable that came in the PS5 box is canonical.")
        return 1

    print(f">> FAIL  rate {rate:.0f} Hz — controller not enumerating as HID.")
    print("   Check Device Manager: controller should appear under")
    print("   'Human Interface Devices' as 'Sony DualSense Edge Wireless Controller'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
