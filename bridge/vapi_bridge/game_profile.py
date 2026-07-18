"""
Phase 51: Game-Aware Profile System.

Maps game titles to button semantics, L5 priority overrides, and L6-Passive config.
Registry is populated at import time. Query via get_profile() / get_profile_or_none().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GameProfile:
    """Immutable game-specific biometric profiling configuration."""

    profile_id: str
    """Unique slug, e.g. 'ncaa_cfb_26'."""

    display_name: str
    """Human-readable name shown in dashboard and agent responses."""

    publisher: str
    """Game publisher / developer."""

    platform: str
    """Target platform, e.g. 'ps5'."""

    # --- L5 oracle ---
    l5_button_priority: List[str]
    """
    Ordered list of button names for L5 temporal rhythm scoring.
    First button with >= 20 samples wins. Names must match TemporalRhythmOracle
    _DEQUE_MAP keys: 'cross', 'l2_dig', 'r2', 'triangle'.
    """

    # --- L6-Passive ---
    l6_passive_enabled: bool
    """
    When True, the bridge passively measures sprint-button onset timing per press.
    No controller writes — zero conflict with PS5 Bluetooth haptics.
    """

    l6_passive_button: str
    """Which button to observe for L6-Passive. Typically 'r2' (sprint)."""

    l6_passive_ema_alpha: float
    """EMA smoothing factor for running baseline. Lower = slower adaptation."""

    l6_passive_baseline_n: int
    """Number of bootstrap presses before EMA kicks in."""

    l6_passive_flag_ratio: float
    """
    Onset_ms / baseline_ms ratio that triggers a 'resistance event' flag.
    E.g. 1.5 = onset 50% slower than personal baseline = PS5 haptic resistance likely.
    """

    # --- Semantic button map ---
    button_map: Dict[str, str]
    """
    Maps button identifiers to game-semantic role descriptions.
    Used by BridgeAgent to give game-contextual explanations.
    e.g. {'r2': 'Sprint / Bullet pass modifier', 'cross': 'Snap / Receiver select'}
    """


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[str, GameProfile] = {}


def register_profile(profile: GameProfile) -> None:
    """Register a GameProfile. Overwrites if profile_id already exists."""
    _REGISTRY[profile.profile_id] = profile


def get_profile(profile_id: str) -> GameProfile:
    """Return profile by ID. Raises KeyError if not found."""
    return _REGISTRY[profile_id]


def get_profile_or_none(profile_id: str) -> Optional[GameProfile]:
    """Return profile by ID, or None if not registered."""
    return _REGISTRY.get(profile_id)


def all_profiles() -> List[GameProfile]:
    """Return all registered profiles (copy of values)."""
    return list(_REGISTRY.values())


# ---------------------------------------------------------------------------
# NCAA College Football 26
# ---------------------------------------------------------------------------

NCAA_CFB_26 = GameProfile(
    profile_id="ncaa_cfb_26",
    display_name="NCAA College Football 26",
    publisher="EA Sports",
    platform="ps5",

    # R2 = sprint (primary, sustained holds 200-2500ms, every running/defensive play)
    # Cross = snap confirmation + receiver selection (high frequency taps)
    # L2_dig = lob pass modifier + ball protection (moderate, short holds)
    # Triangle = switch player / stiff arm / throw away (situational)
    l5_button_priority=["r2", "cross", "l2_dig", "triangle"],

    l6_passive_enabled=True,
    l6_passive_button="r2",
    l6_passive_ema_alpha=0.15,   # slow EMA — sprint hold times vary widely by game situation
    l6_passive_baseline_n=20,    # bootstrap on first 20 sprint presses
    l6_passive_flag_ratio=1.5,   # 50% slower onset than personal mean = resistance event

    button_map={
        "r2":       "Sprint / Bullet pass modifier (primary — held every play)",
        "l2":       "Lob pass modifier / Ball protection / Strip attempt",
        "cross":    "Snap ball / Receiver select / Dive / Low tackle",
        "circle":   "QB slide / Pitch / Receiver (high routes)",
        "square":   "Juke cut / Speed rush / Receiver (low routes)",
        "triangle": "Switch player / Stiff arm / Throw away",
        "r1":       "Pass protection / Hot route / Hurry up offense",
        "l1":       "Audible / Flip play / Motion",
        "r_stick":  "Ball carrier moves (juke, spin, truck)",
        "l_stick":  "Player movement (360 analog)",
        "d_pad":    "Formation / Play selection / Snap count",
    },
)

register_profile(NCAA_CFB_26)


# ---------------------------------------------------------------------------
# Call of Duty: Warzone (2026-06-05)
# ---------------------------------------------------------------------------
#
# First-person shooter / battle-royale profile. Distinct biometric signature
# vs. NCAA CFB 26 — the primary L6-Passive observation window shifts from
# R2 (sprint hold) to L2 (Aim Down Sights hold) because ADS is the dominant
# sustained-trigger event during firefights. R2 is also held heavily (fire)
# but fire-pull cadence is too event-driven to baseline cleanly for the
# resistance-event flag; ADS holds are 1-3 second sustained pulls with a
# clear onset edge.
#
# Button priority for L5 temporal rhythm reflects Warzone meta:
#   r2  (fire)         — primary, near-constant in active engagements
#   l2  (ADS)          — secondary, sustained during gunfights
#   cross (jump)       — moderate, movement / movement-tech
#   square (reload)    — situational but periodic
COD_WARZONE = GameProfile(
    profile_id="cod_warzone",
    display_name="Call of Duty: Warzone",
    publisher="Activision",
    platform="ps5",

    l5_button_priority=["r2", "l2_dig", "cross", "square"],

    l6_passive_enabled=True,
    l6_passive_button="l2_dig",   # ADS hold — sustained-trigger pull during gunfights
    l6_passive_ema_alpha=0.18,    # slightly faster EMA than NCAA — ADS durations are
                                  # more stable per engagement, so baseline converges sooner
    l6_passive_baseline_n=20,     # same bootstrap as NCAA
    l6_passive_flag_ratio=1.5,    # same resistance-event threshold

    button_map={
        "r2":       "Fire / Primary shoot (held during sustained fire; tapped for burst)",
        "l2":       "Aim Down Sights (sustained 1-3s during engagements)",
        "cross":    "Jump / Mantle / Tactical movement",
        "circle":   "Crouch / Prone (toggle/hold) / Slide cancel",
        "square":   "Reload / Interact / Use field upgrade",
        "triangle": "Weapon swap / Pickup",
        "r1":       "Melee / Knife (situational close-quarters)",
        "l1":       "Throw equipment / Lethal grenade",
        "r_stick":  "Camera look / R3-click marker ping",
        "l_stick":  "Player movement / L3-click tactical sprint",
        "d_pad":    "Loadout cycle / Tactical / Killstreaks / Ping wheel",
    },
)

register_profile(COD_WARZONE)


# ---------------------------------------------------------------------------
# EA Sports College Football 27 (2026-07-18; A2A cfb27 r02 — grok-steered v1)
# ---------------------------------------------------------------------------
#
# Released mid-July 2026. Web-researched input deltas vs CFB 26 (cfb27-r01 D1-D4):
#   D1  Tackle Stick — the right stick is ACTIVE in-play on BOTH sides (defense: hit/cut/lunge/wrap
#       + rip/bull-rush/club-swim; offense: ball-carrier moves + R2+RS QB specials). The CFB-26
#       "dead-zone stick game" L2C assumption does NOT transfer: L2C may compute non-None values
#       in 27. Advisory weight (0.10) unchanged — a telemetry-shape note, not a reweight.
#   D2  Timing-based catching — RELEASE the catch button (triangle/cross) inside a green window.
#       New precision-timing input; L5 sees shifted press/release IBI shapes on catch buttons.
#   D3  QB Sneak Meter + kick meters — pre-snap timing-meter inputs (precision windows).
#   D4  L2 repurposed — free-form pass placement (offense) / strafe (defense): more aim-like holds.
#
# HONEST v1 (grok cfb27-r02 A): R2 IS STILL SPRINT on both sides, so the 26 biometric config
# transfers — same L5 priority (priority is sample sufficiency, not full scheme ontology; D2/D4
# change the RHYTHM SHAPE of L2/catch buttons, not which button wins bootstrap first) and the same
# L6-Passive R2 observation. Reorders/reweights WAIT for a CFB-27 corpus (N-gated, never assumed).
NCAA_CFB_27 = GameProfile(
    profile_id="ncaa_cfb_27",
    display_name="EA Sports College Football 27",
    publisher="EA Sports",
    platform="ps5",

    # R2 sprint verified still primary in 27 (controls research 2026-07-18) — clone of 26 priority.
    l5_button_priority=["r2", "cross", "l2_dig", "triangle"],

    l6_passive_enabled=True,
    l6_passive_button="r2",
    l6_passive_ema_alpha=0.15,   # same as 26 — sprint-hold variance shape unchanged by D1-D4
    l6_passive_baseline_n=20,
    l6_passive_flag_ratio=1.5,

    button_map={
        "r2":       "Sprint / Bullet pass modifier (primary — held every play; unchanged from 26)",
        "l2":       "Free-form pass placement (off) / Strafe (def) — D4: more aim-like sustained holds",
        "cross":    "Snap ball / Receiver select / Possession catch (D2: timing-RELEASE window)",
        "circle":   "QB slide / Pitch / Receiver routes",
        "square":   "Juke cut / Speed rush / Aggressive-dive tackle",
        "triangle": "Switch player / Aggressive catch (D2: timing-RELEASE window) / Throw away",
        "r1":       "Fake snap / Defensive keys / Hot route",
        "l1":       "Custom adjustments / Audible / Motion",
        "r_stick":  "D1 ACTIVE IN-PLAY: Tackle Stick (hit/cut/lunge/wrap) + rip/club-swim (def); "
                    "ball-carrier moves + R2+RS QB specials (off) — NOT dead-zone in 27",
        "l_stick":  "Player movement (360 analog)",
        "d_pad":    "Formation / Play selection / Coverage shells",
    },
)

register_profile(NCAA_CFB_27)
