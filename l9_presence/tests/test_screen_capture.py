"""Deterministic tests for the de-risk black-frame guard (numpy-only; no hardware)."""
import numpy as np

from l9_presence.screen_capture import is_black_frame


def test_pure_black_is_black():
    assert is_black_frame(np.zeros((180, 320, 3), dtype=np.uint8)) is True


def test_none_or_empty_is_black():
    assert is_black_frame(None) is True
    assert is_black_frame(np.zeros((0,), dtype=np.uint8)) is True


def test_bright_scene_not_black():
    f = np.full((180, 320, 3), 120, dtype=np.uint8)
    assert is_black_frame(f) is False


def test_dark_but_real_scene_not_black():
    # a genuinely dark game scene: low mean but plenty of non-trivial pixels
    rng = np.random.default_rng(0)
    f = (rng.integers(20, 90, size=(180, 320, 3))).astype(np.uint8)
    assert is_black_frame(f) is False


def test_overlay_black_with_few_stray_pixels_is_black():
    # protected-surface signature: ~all black with a tiny sprinkle of bright pixels
    f = np.zeros((180, 320, 3), dtype=np.uint8)
    f[0, :5, :] = 200  # < 2% active
    assert is_black_frame(f) is True


def test_wgc_listed_iff_available():
    import l9_presence.screen_capture as sc
    assert ("wgc" in sc.available_backends()) == sc._WGC


def test_unavailable_backend_raises_clear_error():
    import pytest
    from l9_presence.screen_capture import ScreenCapturer
    with pytest.raises(RuntimeError):
        ScreenCapturer(backend="does_not_exist")
