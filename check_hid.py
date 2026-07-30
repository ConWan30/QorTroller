"""Check for DualShock Edge via HID."""
import sys, subprocess

# Try pywinusb first
try:
    import pywinusb.hid as hid
    all_devices = hid.HidDeviceFilter().get_devices()
    print(f"Total HID devices via pywinusb: {len(all_devices)}")
    for d in all_devices:
        vid = d.vendor_id
        pid = d.product_id
        name = d.product_name or "Unknown"
        print(f"  VID={hex(vid)} PID={hex(pid)} {name}")
        if vid == 0x054C and pid in (0x05C4, 0x09CC, 0x0CE6, 0x0DF2):
            print("  *** DUALSHOCK EDGE DETECTED ***")
except Exception as e:
    print(f"pywinusb error: {e}")

# Try hid library
try:
    import hid
    devices = hid.enumerate()
    print(f"\nTotal HID devices via hid: {len(devices)}")
    for d in devices:
        vid = d.get('vendor_id', 0)
        pid = d.get('product_id', 0)
        name = d.get('product_string', 'Unknown')
        print(f"  VID={hex(vid)} PID={hex(pid)} {name}")
        if vid == 0x054C and pid in (0x05C4, 0x09CC, 0x0CE6, 0x0DF2):
            print("  *** DUALSHOCK EDGE DETECTED ***")
except Exception as e:
    print(f"hid error: {e}")

# Try PowerShell to check USB devices
print("\nPowerShell USB check:")
try:
    cmd = ["powershell", "-Command", "Get-PnpDevice -Class HIDClass | Select-Object Status, FriendlyName, InstanceId | Format-Table -AutoSize"]
    result = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=10)
    print(result.stdout[:2000])
except Exception as e:
    print(f"PowerShell error: {e}")