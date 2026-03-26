"""
VAPI Phase 69 — VAPIDataCurator SDK Client
==========================================

Wraps all DataCuratorAgent REST endpoints and provides a Pythonic interface
for manufacturers, developers, and gamers querying VAPI data sovereignty state.

Data access tiers (matches VAPIDataMarketplace.sol):
    MANUFACTURER — hardware OEMs (all data classes)
    DEVELOPER    — game studios, tournament operators (session, proof, oracle, ruling, reward)
    GAMER        — DualShock Edge owners (own session + biometric data only, free)

Never raises to caller — all methods return error field in response dict on failure.

Classes:
    VAPIDataCurator   — Primary client: data lineage, token eligibility, oracle state, reward score
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

__version__ = "3.0.0-phase69"

_DEFAULT_BASE_URL = "http://localhost:8765"
_DEFAULT_TIMEOUT  = 15


@dataclass
class DataLineageEntry:
    """A single data lineage record linking session → proof → ruling → reward."""
    id:             int
    device_id:      str
    record_hash:    Optional[str]
    taxonomy_class: str       # one of DATA_TAXONOMY keys
    quality_index:  float     # 0.0–1.0
    curator_note:   str
    created_at:     float


@dataclass
class TokenEligibility:
    """Token eligibility state computed by DataCuratorAgent."""
    device_id:           str
    nominal_sessions:    int
    clean_streak:        int
    passport_held:       bool
    enrollment_complete: bool
    mpc_verified:        bool
    gate_passed:         bool
    base_multiplier:     float
    total_multiplier:    float
    eligibility_score:   float
    last_computed_at:    float


@dataclass
class RewardScore:
    """Full reward calculation with factor breakdown."""
    device_id:           str
    nominal_sessions:    int
    clean_streak:        int
    passport_held:       bool
    enrollment_complete: bool
    mpc_verified:        bool
    gate_passed:         bool
    base_multiplier:     float
    total_multiplier:    float
    eligibility_score:   float
    multiplier_breakdown: dict = field(default_factory=dict)
    error:               Optional[str] = None


class VAPIDataCurator:
    """Phase 69 — DataCurator SDK client.

    Wraps all /curator/* endpoints exposed by the VAPI bridge.

    Args:
        base_url:  Bridge base URL (default: http://localhost:8765)
        api_key:   Operator API key (required for all endpoints)
        timeout:   Request timeout in seconds (default: 15)

    All methods are synchronous and never raise — returns error field on failure.
    """

    DATA_TAXONOMY = {
        "SESSION_DATA":     "Raw PoAC records, 228B wire format, inference codes",
        "CALIBRATION_DATA": "L4 thresholds (7.009/5.367), EMA tracks, N=74 corpus",
        "PROOF_DATA":       "Groth16 ZK proofs, Poseidon commitments, MPC ceremony",
        "RULING_DATA":      "Agent rulings, enforcement streaks, credential suspensions",
        "BIOMETRIC_DATA":   "12-feature vectors, tremor FFT, jitter variance IBI",
        "ORACLE_DATA":      "Published oracle values, on-chain update history",
        "REWARD_DATA":      "Token distribution records, eligibility verdicts, multipliers",
    }

    # Data tier — mirrors VAPIDataMarketplace.sol LicenseTier enum
    TIER_MANUFACTURER = "MANUFACTURER"
    TIER_DEVELOPER    = "DEVELOPER"
    TIER_GAMER        = "GAMER"

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        api_key: str = "",
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key  = api_key
        self._timeout  = timeout

    # -----------------------------------------------------------------------
    # Core endpoints
    # -----------------------------------------------------------------------

    def get_data_lineage(self, device_id: str, limit: int = 50) -> dict:
        """Fetch the full data lineage graph for a device.

        Returns:
            {
              "device_id": str,
              "lineage_count": int,
              "lineage": [DataLineageEntry as dict, ...]
            }
            On error: {"error": str, "device_id": str}
        """
        url = f"{self._base_url}/operator/curator/data-lineage/{device_id}"
        params = f"api_key={self._api_key}&limit={limit}"
        return self._get(f"{url}?{params}", device_id=device_id)

    def get_token_eligibility(self, device_id: str) -> dict:
        """Fetch token eligibility score + multiplier breakdown for a device.

        Returns:
            {
              "device_id": str,
              "eligibility": {
                "nominal_sessions": int,
                "clean_streak": int,
                "passport_held": bool,
                "enrollment_complete": bool,
                "mpc_verified": bool,
                "gate_passed": bool,
                "base_multiplier": float,
                "total_multiplier": float,
                "eligibility_score": float,
                "last_computed_at": float,
              }
            }
            eligibility is None if device has no computed state yet.
            On error: {"error": str, "device_id": str}
        """
        url = f"{self._base_url}/operator/curator/token-eligibility/{device_id}"
        params = f"api_key={self._api_key}"
        return self._get(f"{url}?{params}", device_id=device_id)

    def get_oracle_state(self, oracle_type: str, limit: int = 50) -> dict:
        """Fetch recent oracle publication log for a given oracle type.

        Args:
            oracle_type: "HUMANITY" | "RULING" | "PASSPORT"
            limit:       Max records to return (default: 50)

        Returns:
            {
              "oracle_type": str,
              "publication_count": int,
              "publications": [...]
            }
            On error: {"error": str, "oracle_type": str}
        """
        oracle_type = oracle_type.upper()
        url = f"{self._base_url}/operator/curator/oracle-state/{oracle_type}"
        params = f"api_key={self._api_key}&limit={limit}"
        return self._get(f"{url}?{params}", oracle_type=oracle_type)

    def compute_reward_score(self, device_id: str) -> dict:
        """Return full reward score breakdown for a device from token_eligibility table.

        This is a client-side computation from cached eligibility state — not a live
        oracle query. Calls get_token_eligibility() and enriches with multiplier breakdown.

        Returns:
            {
              "device_id": str,
              "nominal_sessions": int,
              "total_multiplier": float,
              "eligibility_score": float,
              "multiplier_breakdown": {
                "passport": "1.5×",
                "enrollment": "2.0×",
                "clean_streak": "2.5×",
                "mpc_verified": "1.25×",
                "gate_passed": "3.0×",
              },
              ...
            }
            On error: {"error": str, "device_id": str}
        """
        try:
            resp = self.get_token_eligibility(device_id)
            if "error" in resp:
                return resp
            elig = resp.get("eligibility")
            if elig is None:
                return {
                    "device_id":     device_id,
                    "eligibility":   None,
                    "error":         "No eligibility state found — DataCuratorAgent not yet run",
                }
            breakdown = {}
            if elig.get("passport_held"):
                breakdown["passport"] = "1.50×"
            if elig.get("enrollment_complete"):
                breakdown["enrollment"] = "2.00×"
            if (elig.get("clean_streak") or 0) >= 5:
                breakdown["clean_streak"] = "2.50×"
            if elig.get("mpc_verified"):
                breakdown["mpc_verified"] = "1.25×"
            if elig.get("gate_passed"):
                breakdown["gate_passed"] = "3.00×"

            return {
                "device_id":           device_id,
                "nominal_sessions":    elig.get("nominal_sessions", 0),
                "clean_streak":        elig.get("clean_streak", 0),
                "passport_held":       elig.get("passport_held", False),
                "enrollment_complete": elig.get("enrollment_complete", False),
                "mpc_verified":        elig.get("mpc_verified", False),
                "gate_passed":         elig.get("gate_passed", False),
                "base_multiplier":     elig.get("base_multiplier", 1.0),
                "total_multiplier":    elig.get("total_multiplier", 1.0),
                "eligibility_score":   elig.get("eligibility_score", 0.0),
                "multiplier_breakdown": breakdown,
                "last_computed_at":    elig.get("last_computed_at"),
            }
        except Exception as exc:
            return {"error": str(exc), "device_id": device_id}

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _get(self, url: str, **error_ctx) -> dict:
        """Execute a GET request. Never raises — returns error dict on failure."""
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body).get("detail", body)
            except Exception:
                detail = body
            return {"error": f"HTTP {exc.code}: {detail}", **error_ctx}
        except Exception as exc:
            return {"error": str(exc), **error_ctx}
