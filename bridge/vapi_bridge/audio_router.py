"""
bridge/vapi_bridge/audio_router.py — Windows Core Audio default device router.

When the DualSense Edge connects via USB, Windows may auto-switch the default
audio output to the controller's audio endpoint ("Speakers (DualSense Edge Wirele)").
If the user has no headphones plugged into the controller's 3.5mm jack, all game
audio is silenced.

This module detects that condition at bridge startup and restores game audio to
the user's preferred device (default: Realtek system speakers).

Mechanism: IPolicyConfigVista COM interface (Windows Vista through Windows 11),
vtable index 13: SetDefaultEndpoint(LPCWSTR pwstrDeviceId, ERole role).
IMMDeviceEnumerator COM interface, vtable index 4: GetDefaultAudioEndpoint.

Platform: Windows only — graceful no-op on all other platforms.
No external dependencies — uses ctypes + winreg only (both Python built-in).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import sys
import winreg
from dataclasses import dataclass, field
from typing import Optional

_log = logging.getLogger(__name__)
_IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Keywords for device classification
# ---------------------------------------------------------------------------

_DUALSENSE_KEYWORDS   = ("DualSense", "DualShock", "VID_054C&PID_0DF2")
_SYSTEM_AUDIO_KEYWORDS = ("Realtek", "High Definition Audio")

# Registry property key names (PKEY constants)
_PKEY_WMM_SHORT_NAME   = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"   # short name e.g. "Speakers"
_PKEY_DRIVER_PRODUCT   = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"   # driver product name
_PKEY_USB_HWID         = "{b3f8fa53-0004-438e-9003-51a46e139bfc},39"  # USB VID/PID hardware ID
_PKEY_WASAPI_ID_FULL   = "{9D631510-92A8-4a79-A79E-A83812C9C119},1"   # full WASAPI endpoint ID

# COM constants
_CLSCTX_ALL = 0x17   # INPROC_SERVER | INPROC_HANDLER | LOCAL_SERVER | REMOTE_SERVER


# ---------------------------------------------------------------------------
# AudioDevice data model
# ---------------------------------------------------------------------------

@dataclass
class AudioDevice:
    """Registry-sourced audio render endpoint descriptor."""
    guid:          str    # Registry key GUID, e.g. "{17490855-...}"
    wasapi_id:     str    # Full WASAPI endpoint ID: "{0.0.0.00000000}.{guid}"
    friendly_name: str    # Short WinMM name, e.g. "Speakers"
    driver_name:   str    # Driver product name, e.g. "Realtek(R) Audio"
    usb_id:        str    # USB hardware ID if USB device, else ""
    is_dualsense:  bool   = field(init=False)
    is_system_audio: bool = field(init=False)

    def __post_init__(self) -> None:
        text = (self.friendly_name + " " + self.driver_name + " " + self.usb_id).lower()
        self.is_dualsense    = any(k.lower() in text for k in _DUALSENSE_KEYWORDS)
        self.is_system_audio = any(k.lower() in text for k in _SYSTEM_AUDIO_KEYWORDS)


# ---------------------------------------------------------------------------
# Registry device enumeration
# ---------------------------------------------------------------------------

def _read_render_devices() -> list[AudioDevice]:
    """
    Read all audio render (output) device records from the Windows registry.
    Returns empty list on error or non-Windows platforms.
    """
    if not _IS_WINDOWS:
        return []
    devices: list[AudioDevice] = []
    reg_base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_base) as base_key:
            i = 0
            while True:
                try:
                    guid_key = winreg.EnumKey(base_key, i)
                    i += 1
                except OSError:
                    break
                props: dict[str, str] = {}
                try:
                    prop_path = reg_base + "\\" + guid_key + "\\Properties"
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, prop_path) as pk:
                        j = 0
                        while True:
                            try:
                                vn, vd, _vt = winreg.EnumValue(pk, j)
                                j += 1
                                if isinstance(vd, str):
                                    props[vn] = vd
                            except OSError:
                                break
                except OSError:
                    pass

                friendly_name = props.get(_PKEY_WMM_SHORT_NAME, "")
                driver_name   = props.get(_PKEY_DRIVER_PRODUCT,  "")
                usb_id        = props.get(_PKEY_USB_HWID,         "")
                wasapi_id     = props.get(
                    _PKEY_WASAPI_ID_FULL,
                    "{0.0.0.00000000}.{" + guid_key + "}",
                )
                devices.append(AudioDevice(
                    guid=guid_key,
                    wasapi_id=wasapi_id,
                    friendly_name=friendly_name,
                    driver_name=driver_name,
                    usb_id=usb_id,
                ))
    except Exception as exc:
        _log.debug("audio_router: registry enumeration failed: %s", exc)
    return devices


# ---------------------------------------------------------------------------
# Windows Core Audio COM helpers (ctypes, no external dependencies)
# ---------------------------------------------------------------------------

class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(s: str) -> _GUID:
    s = s.strip("{}")
    p = s.split("-")
    g = _GUID()
    g.Data1 = int(p[0], 16)
    g.Data2 = int(p[1], 16)
    g.Data3 = int(p[2], 16)
    d4 = bytes.fromhex(p[3] + p[4])
    g.Data4 = (ctypes.c_ubyte * 8)(*d4)
    return g


_CLSID_MMDeviceEnum       = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
_IID_IMMDeviceEnumerator  = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
_CLSID_PolicyConfigVista  = _guid("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}")
_IID_IUnknown             = _guid("{00000000-0000-0000-C000-000000000046}")


def _get_default_endpoint_id() -> str:
    """
    Return the WASAPI device ID of the current default render endpoint (eConsole role).
    Uses IMMDeviceEnumerator::GetDefaultAudioEndpoint (vtable[4])
    then IMMDevice::GetId (vtable[5]).
    Returns "" on failure.
    """
    if not _IS_WINDOWS:
        return ""
    try:
        ole32 = ctypes.OleDLL("ole32")
        ole32.CoInitializeEx(None, 0)

        enum_ptr = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(_CLSID_MMDeviceEnum),
            None,
            _CLSCTX_ALL,
            ctypes.byref(_IID_IMMDeviceEnumerator),
            ctypes.byref(enum_ptr),
        )
        if hr != 0 or not enum_ptr.value:
            return ""

        vtbl = ctypes.cast(
            ctypes.cast(enum_ptr, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p),
        )

        # vtable[4]: GetDefaultAudioEndpoint(EDataFlow=0 eRender, ERole=0 eConsole, IMMDevice**)
        _GetDefault = ctypes.WINFUNCTYPE(
            ctypes.HRESULT,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_void_p),
        )(vtbl[4])

        dev_ptr = ctypes.c_void_p()
        hr = _GetDefault(enum_ptr.value, 0, 0, ctypes.byref(dev_ptr))
        if hr != 0 or not dev_ptr.value:
            return ""

        dev_vtbl = ctypes.cast(
            ctypes.cast(dev_ptr, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p),
        )

        # vtable[5]: GetId(LPWSTR*)
        _GetId = ctypes.WINFUNCTYPE(
            ctypes.HRESULT,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        )(dev_vtbl[5])

        id_ptr = ctypes.c_wchar_p()
        hr = _GetId(dev_ptr.value, ctypes.byref(id_ptr))
        device_id = id_ptr.value or ""

        # Free CoTaskMem
        try:
            ctypes.windll.ole32.CoTaskMemFree(id_ptr)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Release IMMDevice
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(dev_vtbl[2])(dev_ptr.value)
        # Release IMMDeviceEnumerator
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(enum_ptr.value)

        return device_id

    except Exception as exc:
        _log.debug("audio_router: GetDefaultAudioEndpoint failed: %s", exc)
        return ""


def _set_default_endpoint(wasapi_device_id: str) -> bool:
    """
    Call IPolicyConfigVista::SetDefaultEndpoint (vtable[13]) for all three
    ERole values (eConsole=0, eMultimedia=1, eCommunications=2).
    Returns True if all three calls succeed (hr==0).

    CLSID: {870AF99C-171D-4F9E-AF0D-E63DF40C2BC9} (works Vista → Windows 11)
    Vtable index 13 is SetDefaultEndpoint on all modern Windows versions.
    """
    if not _IS_WINDOWS:
        return False
    try:
        ole32 = ctypes.OleDLL("ole32")
        ole32.CoInitializeEx(None, 0)

        pc_ptr = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(_CLSID_PolicyConfigVista),
            None,
            _CLSCTX_ALL,
            ctypes.byref(_IID_IUnknown),
            ctypes.byref(pc_ptr),
        )
        if hr != 0 or not pc_ptr.value:
            _log.debug(
                "audio_router: CoCreateInstance PolicyConfigVista hr=0x%08x", hr & 0xFFFFFFFF
            )
            return False

        vtbl = ctypes.cast(
            ctypes.cast(pc_ptr, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p),
        )

        # vtable[13]: SetDefaultEndpoint(LPCWSTR pwstrDeviceId, ERole role)
        _SetDefaultEndpoint = ctypes.WINFUNCTYPE(
            ctypes.HRESULT,
            ctypes.c_void_p,    # this
            ctypes.c_wchar_p,   # pwstrDeviceId
            ctypes.c_uint,      # ERole
        )(vtbl[13])

        success = True
        for role in (0, 1, 2):  # eConsole, eMultimedia, eCommunications
            hr = _SetDefaultEndpoint(pc_ptr.value, wasapi_device_id, role)
            if hr != 0:
                _log.debug(
                    "audio_router: SetDefaultEndpoint role=%d hr=0x%08x", role, hr & 0xFFFFFFFF
                )
                success = False

        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(pc_ptr.value)
        return success

    except Exception as exc:
        _log.warning("audio_router: SetDefaultEndpoint failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# AudioRouteResult
# ---------------------------------------------------------------------------

class AudioRouteResult:
    """Result of an ensure_game_audio() call."""
    __slots__ = ("success", "previous_device_id", "current_device_id", "action", "error")

    def __init__(self) -> None:
        self.success:            bool         = False
        self.previous_device_id: str          = ""
        self.current_device_id:  str          = ""
        self.action:             str          = "none"
        self.error:              Optional[str] = None


# ---------------------------------------------------------------------------
# AudioRouter — public API
# ---------------------------------------------------------------------------

class AudioRouter:
    """
    VAPI DualSense audio passthrough router.

    On bridge startup, checks whether Windows has switched the default audio
    output to the DualSense Edge. If so, and preferred="system", routes audio
    back to the system (Realtek) device so game sound plays through speakers
    or external headphones.

    preferred values:
        "system"   — prefer Realtek/built-in audio (default, recommended)
        "dualsense" — prefer DualSense headphone jack (user has headphones in controller)
        "keep"     — do not change audio routing

    Usage:
        router = AudioRouter(preferred="system")
        result = router.ensure_game_audio()   # call at DualShock connect
        # ... session runs ...
        router.restore()                       # call at bridge shutdown
    """

    def __init__(self, preferred: str = "system") -> None:
        self._preferred = preferred
        self._saved_id  = ""    # WASAPI ID before any routing change
        self._changed   = False

    # ------------------------------------------------------------------ #
    # Introspection helpers
    # ------------------------------------------------------------------ #

    def get_devices(self) -> list[AudioDevice]:
        """Return all registered audio render endpoints from Windows registry."""
        return _read_render_devices()

    def get_current_default_id(self) -> str:
        """Return WASAPI ID of the current default render endpoint, or ''."""
        return _get_default_endpoint_id()

    def get_current_default_device(self) -> Optional[AudioDevice]:
        """Return the AudioDevice for the current default output, or None."""
        current_id = self.get_current_default_id()
        if not current_id:
            return None
        devices = self.get_devices()
        return next(
            (d for d in devices if d.wasapi_id.lower() in current_id.lower()),
            None,
        )

    # ------------------------------------------------------------------ #
    # Routing logic
    # ------------------------------------------------------------------ #

    def ensure_game_audio(self) -> AudioRouteResult:
        """
        Ensure game audio plays through the correct device.

        If preferred="system": detect if DualSense captured default → switch to Realtek.
        If preferred="dualsense": ensure DualSense is default (for controller headphones).
        If preferred="keep": no-op.

        Saves current state for restore() on bridge shutdown.
        """
        result = AudioRouteResult()

        if not _IS_WINDOWS:
            result.action  = "skipped_platform"
            result.success = True
            return result

        if self._preferred == "keep":
            result.action  = "skipped_keep"
            result.success = True
            return result

        devices    = self.get_devices()
        current_id = self.get_current_default_id()
        result.previous_device_id = current_id

        current_dev = next(
            (d for d in devices
             if current_id and d.wasapi_id.lower() in current_id.lower()),
            None,
        )

        if self._preferred == "dualsense":
            ds_dev = next((d for d in devices if d.is_dualsense), None)
            if ds_dev is None:
                result.action = "no_dualsense_device_found"
                result.error  = "No DualSense audio endpoint found in registry"
                return result
            if current_dev and current_dev.is_dualsense:
                result.action             = "already_dualsense"
                result.current_device_id  = current_id
                result.success            = True
                return result
            self._saved_id = current_id
            ok = _set_default_endpoint(ds_dev.wasapi_id)
            result.action            = "switched_to_dualsense"
            result.current_device_id = ds_dev.wasapi_id
            result.success           = ok
            if ok:
                self._changed = True
                _log.info(
                    "audio_router: switched default audio → DualSense (%s | %s)",
                    ds_dev.friendly_name, ds_dev.driver_name,
                )
            else:
                result.error = "IPolicyConfigVista::SetDefaultEndpoint failed (dualsense)"
            return result

        # preferred == "system"
        if current_dev is None or not current_dev.is_dualsense:
            # Current default is already a non-DualSense device — nothing to do
            result.action            = "no_change_needed"
            result.current_device_id = current_id
            result.success           = True
            _log.debug(
                "audio_router: default audio is not DualSense (%s) — no change",
                (current_dev.driver_name if current_dev else "unknown"),
            )
            return result

        # DualSense is current default — find best system audio device
        # Prefer: Realtek Speakers > Realtek Headphones > any system audio
        sys_dev = (
            next((d for d in devices
                  if d.is_system_audio and "speaker" in d.friendly_name.lower()), None)
            or next((d for d in devices if d.is_system_audio), None)
        )
        if sys_dev is None:
            result.action  = "no_system_device_found"
            result.error   = "No Realtek/system audio device found to restore game audio"
            result.success = False
            _log.warning("audio_router: DualSense is default audio but no system device found")
            return result

        self._saved_id = current_id
        ok = _set_default_endpoint(sys_dev.wasapi_id)
        result.action            = "switched_to_system"
        result.current_device_id = sys_dev.wasapi_id
        result.success           = ok
        if ok:
            self._changed = True
            _log.info(
                "audio_router: DualSense captured default audio → restored to %s (%s)",
                sys_dev.driver_name or sys_dev.friendly_name, sys_dev.wasapi_id,
            )
        else:
            result.error = "IPolicyConfigVista::SetDefaultEndpoint failed (system)"
        return result

    def restore(self) -> bool:
        """
        Restore the audio default device to what it was before ensure_game_audio()
        changed it. Called on bridge shutdown.
        Returns True if nothing to restore or restore succeeded.
        """
        if not self._changed or not self._saved_id:
            return True
        ok = _set_default_endpoint(self._saved_id)
        if ok:
            self._changed = False
            _log.info("audio_router: restored previous default audio endpoint")
        else:
            _log.debug("audio_router: restore() failed — previous device may be disconnected")
        return ok
