"""
bridge/tests/test_phase136_audio_router.py

Phase 136 — DualSense Audio Passthrough Router tests.
8 tests covering AudioDevice classification, AudioRouteResult, AudioRouter
routing modes, registry enumeration, COM helpers (mocked), and config fields.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Windows platform stub — allows import on Linux/macOS in CI
# ---------------------------------------------------------------------------
if sys.platform != "win32":
    _winreg_stub = types.ModuleType("winreg")
    _winreg_stub.HKEY_LOCAL_MACHINE = 0x80000002
    _winreg_stub.OpenKey  = MagicMock(side_effect=OSError("stub"))
    _winreg_stub.EnumKey  = MagicMock(side_effect=OSError("stub"))
    _winreg_stub.EnumValue = MagicMock(side_effect=OSError("stub"))
    sys.modules["winreg"] = _winreg_stub

from bridge.vapi_bridge.audio_router import (  # noqa: E402
    AudioDevice,
    AudioRouteResult,
    AudioRouter,
    _read_render_devices,
    _get_default_endpoint_id,
    _set_default_endpoint,
)


class TestAudioDevice(unittest.TestCase):
    """T136-1 — AudioDevice classification from name fields."""

    def test_dualsense_detected_by_name(self):
        dev = AudioDevice(
            guid="{1234}",
            wasapi_id="{0.0.0.00000000}.{1234}",
            friendly_name="Speakers",
            driver_name="DualSense Edge Wireless Controller",
            usb_id="",
        )
        self.assertTrue(dev.is_dualsense)
        self.assertFalse(dev.is_system_audio)

    def test_system_audio_detected_by_realtek(self):
        dev = AudioDevice(
            guid="{5678}",
            wasapi_id="{0.0.0.00000000}.{5678}",
            friendly_name="Speakers (Realtek(R) Audio)",
            driver_name="Realtek(R) Audio",
            usb_id="",
        )
        self.assertFalse(dev.is_dualsense)
        self.assertTrue(dev.is_system_audio)

    def test_usb_vid_pid_triggers_dualsense(self):
        dev = AudioDevice(
            guid="{ABCD}",
            wasapi_id="{0.0.0.00000000}.{ABCD}",
            friendly_name="Headset Earphone",
            driver_name="Generic USB Audio",
            usb_id="VID_054C&PID_0DF2",
        )
        self.assertTrue(dev.is_dualsense)

    def test_unknown_device_neither_flag(self):
        dev = AudioDevice(
            guid="{CCCC}",
            wasapi_id="{0.0.0.00000000}.{CCCC}",
            friendly_name="Monitor Speakers",
            driver_name="Generic HDMI Audio",
            usb_id="",
        )
        self.assertFalse(dev.is_dualsense)
        self.assertFalse(dev.is_system_audio)


class TestAudioRouteResult(unittest.TestCase):
    """T136-2 — AudioRouteResult default fields."""

    def test_defaults(self):
        r = AudioRouteResult()
        self.assertFalse(r.success)
        self.assertEqual(r.previous_device_id, "")
        self.assertEqual(r.current_device_id, "")
        self.assertEqual(r.action, "none")
        self.assertIsNone(r.error)

    def test_slots(self):
        r = AudioRouteResult()
        self.assertIn("success", AudioRouteResult.__slots__)
        self.assertIn("action", AudioRouteResult.__slots__)
        self.assertIn("error", AudioRouteResult.__slots__)


class TestAudioRouterKeepMode(unittest.TestCase):
    """T136-3 — preferred='keep' never calls SetDefaultEndpoint."""

    def test_keep_is_noop(self):
        router = AudioRouter(preferred="keep")
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", True):
            with patch("bridge.vapi_bridge.audio_router._get_default_endpoint_id", return_value="") as _gde, \
                 patch("bridge.vapi_bridge.audio_router._set_default_endpoint") as _sde:
                result = router.ensure_game_audio()
        self.assertEqual(result.action, "skipped_keep")
        self.assertTrue(result.success)
        _sde.assert_not_called()


class TestAudioRouterSystemMode(unittest.TestCase):
    """T136-4 — preferred='system': no change when DualSense is NOT default."""

    def _make_realtek_dev(self):
        return AudioDevice(
            guid="{AAA}",
            wasapi_id="{0.0.0.00000000}.{AAA}",
            friendly_name="Speakers",
            driver_name="Realtek(R) Audio",
            usb_id="",
        )

    def test_no_change_when_default_is_realtek(self):
        realtek = self._make_realtek_dev()
        router = AudioRouter(preferred="system")
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", True), \
             patch("bridge.vapi_bridge.audio_router._read_render_devices", return_value=[realtek]), \
             patch("bridge.vapi_bridge.audio_router._get_default_endpoint_id",
                   return_value="{0.0.0.00000000}.{AAA}"), \
             patch("bridge.vapi_bridge.audio_router._set_default_endpoint") as _sde:
            result = router.ensure_game_audio()
        self.assertEqual(result.action, "no_change_needed")
        self.assertTrue(result.success)
        _sde.assert_not_called()

    def test_switches_when_dualsense_is_default(self):
        ds = AudioDevice(
            guid="{DS1}",
            wasapi_id="{0.0.0.00000000}.{DS1}",
            friendly_name="Speakers (DualSense Edge Wirele)",
            driver_name="DualSense Edge Wireless Controller",
            usb_id="",
        )
        realtek = self._make_realtek_dev()
        router = AudioRouter(preferred="system")
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", True), \
             patch("bridge.vapi_bridge.audio_router._read_render_devices", return_value=[ds, realtek]), \
             patch("bridge.vapi_bridge.audio_router._get_default_endpoint_id",
                   return_value="{0.0.0.00000000}.{DS1}"), \
             patch("bridge.vapi_bridge.audio_router._set_default_endpoint", return_value=True) as _sde:
            result = router.ensure_game_audio()
        self.assertEqual(result.action, "switched_to_system")
        self.assertTrue(result.success)
        _sde.assert_called_once_with("{0.0.0.00000000}.{AAA}")
        # Router saved previous ID for restore
        self.assertEqual(router._saved_id, "{0.0.0.00000000}.{DS1}")


class TestAudioRouterRestore(unittest.TestCase):
    """T136-5 — restore() re-sets the previously active endpoint."""

    def test_restore_calls_set_endpoint_with_saved_id(self):
        router = AudioRouter(preferred="system")
        router._saved_id = "{0.0.0.00000000}.{ORIG}"
        router._changed  = True
        with patch("bridge.vapi_bridge.audio_router._set_default_endpoint", return_value=True) as _sde:
            ok = router.restore()
        self.assertTrue(ok)
        _sde.assert_called_once_with("{0.0.0.00000000}.{ORIG}")
        self.assertFalse(router._changed)

    def test_restore_noop_when_not_changed(self):
        router = AudioRouter(preferred="system")
        router._changed = False
        with patch("bridge.vapi_bridge.audio_router._set_default_endpoint") as _sde:
            ok = router.restore()
        self.assertTrue(ok)
        _sde.assert_not_called()


class TestNonWindowsPlatform(unittest.TestCase):
    """T136-6 — graceful no-op on non-Windows platforms."""

    def test_read_devices_returns_empty_on_non_windows(self):
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", False):
            devs = _read_render_devices()
        self.assertEqual(devs, [])

    def test_get_default_returns_empty_on_non_windows(self):
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", False):
            result = _get_default_endpoint_id()
        self.assertEqual(result, "")

    def test_set_default_returns_false_on_non_windows(self):
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", False):
            ok = _set_default_endpoint("{some-id}")
        self.assertFalse(ok)

    def test_ensure_game_audio_skips_platform(self):
        router = AudioRouter(preferred="system")
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", False):
            result = router.ensure_game_audio()
        self.assertEqual(result.action, "skipped_platform")
        self.assertTrue(result.success)


class TestAudioRouterNoSystemDevice(unittest.TestCase):
    """T136-7 — handles registry having DualSense but no Realtek device."""

    def test_no_system_device_found(self):
        ds = AudioDevice(
            guid="{DS1}",
            wasapi_id="{0.0.0.00000000}.{DS1}",
            friendly_name="Speakers (DualSense)",
            driver_name="DualSense Edge Wireless Controller",
            usb_id="",
        )
        router = AudioRouter(preferred="system")
        with patch("bridge.vapi_bridge.audio_router._IS_WINDOWS", True), \
             patch("bridge.vapi_bridge.audio_router._read_render_devices", return_value=[ds]), \
             patch("bridge.vapi_bridge.audio_router._get_default_endpoint_id",
                   return_value="{0.0.0.00000000}.{DS1}"), \
             patch("bridge.vapi_bridge.audio_router._set_default_endpoint") as _sde:
            result = router.ensure_game_audio()
        self.assertEqual(result.action, "no_system_device_found")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        _sde.assert_not_called()


class TestConfigFields(unittest.TestCase):
    """T136-8 — Config env defaults for audio_passthrough_enabled and audio_device_preference."""

    def test_config_audio_fields_default_via_env(self):
        """Default: AUDIO_PASSTHROUGH_ENABLED unset → True, AUDIO_DEVICE_PREFERENCE unset → 'system'."""
        import os
        env = {k: v for k, v in os.environ.items()
               if k not in ("AUDIO_PASSTHROUGH_ENABLED", "AUDIO_DEVICE_PREFERENCE")}
        with patch.dict(os.environ, env, clear=True):
            from bridge.vapi_bridge import config as _cfg_mod
            enabled = _cfg_mod._env_bool("AUDIO_PASSTHROUGH_ENABLED", True)
            pref    = _cfg_mod._env("AUDIO_DEVICE_PREFERENCE", "system")
        self.assertTrue(enabled)
        self.assertEqual(pref, "system")

    def test_config_audio_fields_override_via_env(self):
        """AUDIO_PASSTHROUGH_ENABLED=false, AUDIO_DEVICE_PREFERENCE=keep respected."""
        import os
        from bridge.vapi_bridge import config as _cfg_mod
        with patch.dict(os.environ, {
            "AUDIO_PASSTHROUGH_ENABLED": "false",
            "AUDIO_DEVICE_PREFERENCE": "keep",
        }):
            enabled = _cfg_mod._env_bool("AUDIO_PASSTHROUGH_ENABLED", True)
            pref    = _cfg_mod._env("AUDIO_DEVICE_PREFERENCE", "system")
        self.assertFalse(enabled)
        self.assertEqual(pref, "keep")


if __name__ == "__main__":
    unittest.main()
