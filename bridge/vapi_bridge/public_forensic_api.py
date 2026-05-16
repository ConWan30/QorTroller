"""Phase O5-PUBLIC-VIEWER — Public Forensic Replay-and-Verify sub-app.

Public-readable (no auth) FastAPI sub-app mounted at /public, exposing the
substrate the public "VAPI Etherscan for gameplay" viewer consumes.

Every endpoint here is READ-ONLY, PII-filtered, rate-limited, and
VAME-stamped. Every claim served can be re-derived in any browser via
the corresponding `frontend/src/crypto/vapi_verifier.js` function.

Design discipline:
  - NO `_check_key` / `_check_read_key` calls (auth-leak prevention,
    pinned by INV-PUBLIC-FORENSIC-001 grep CI gate).
  - VAME middleware stamps every JSON response with sidecar headers
    (X-VAME-Version / -Commitment / -Chain-Head / -TS-NS / -Endpoint).
  - Rate-limit per IP via sliding-window (60 req/min default;
    cfg.public_forensic_rate_limit_per_min override).
  - Cache-Control: public on commitment-hex-keyed routes (immutable
    once committed; safe to CDN).
  - 5xx never stamped; bad input returns 404 with {found: False, ...}
    rather than 500 (fail-open at the wire layer).

10 ROUTES:
  GET /public/health                          liveness
  GET /public/algorithms                      14 FROZEN-v1 domain tag manifest
  GET /public/session/{commitment_hex}        composite session payload
  GET /public/vpm/{commitment_hex}            single VPM artifact
  GET /public/vpm/{commitment_hex}/preimage   preimage_json sidecar
  GET /public/gic/{grind_session_id}          GIC chain links + genesis
  GET /public/mlga/{dataproof_hex}            MLGA session row + 9 preimage components
  GET /public/record/{device_id}/{counter}    228-byte PoAC record as binary blob
  GET /public/agent-roots                     Sentry/Guardian/Curator on-chain identity
  GET /public/protocol-state                  PV-CI count + ratios + kill-switch

Reads ONLY existing store helpers + the three new helpers shipped with
this phase (get_session_composite / get_record_raw_bytes /
get_protocol_state_snapshot). No writes anywhere.

WALLET-FREE; CHAIN-READ-ONLY; SQLite-READ-ONLY.
"""
from __future__ import annotations

import asyncio
import collections
import logging
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Path as FPath, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as _StarletteResponse

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FROZEN-v1 cryptographic domain tag manifest — the verifier catalog the
# browser-side `frontend/src/crypto/vapi_verifier.js` mirrors. Every tag
# listed here MUST exist as a byte-literal in its referenced Python source.
# This list is the protocol's published algorithm catalog.
# ---------------------------------------------------------------------------

_FROZEN_V1_ALGORITHMS = [
    {
        "tag":          "VAPI-GIC-GENESIS-v1",
        "tag_length":   19,
        "primitive":    "GIC chain genesis",
        "preimage":     "tag(19B) || grind_session_id_utf8 || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/grind_chain.py",
        "py_function":  "genesis_gic",
    },
    {
        "tag":          "GIC chain step (NO domain tag — prev_gic IS the binding)",
        "tag_length":   0,
        "primitive":    "GIC chain link",
        "preimage":     "prev_gic(32B) || commitment(32B) || verdict_code(1B) "
                        "|| host_state_code(1B) || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/grind_chain.py",
        "py_function":  "compute_gic",
    },
    {
        "tag":          "VAPI-MLGA-SESSION-v1",
        "tag_length":   20,
        "primitive":    "MLGA session dataproof",
        "preimage":     "tag(20B) || start_ts_ns(8B) || end_ts_ns(8B) || "
                        "n_poac(8B) || n_r2(4B) || n_l2(4B) || apop_sha256(32B) "
                        "|| bt_obs(1B) || gic_advances(4B) = 89B",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/mlga_capture.py",
        "py_function":  "compute_mlga_session_dataproof",
    },
    {
        "tag":          "VAPI-WEC-GENESIS-v1",
        "tag_length":   19,
        "primitive":    "Watchdog Event Chain genesis",
        "preimage":     "tag(19B) || grind_session_id_utf8 || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/watchdog_chain.py",
        "py_function":  "genesis_wec",
    },
    {
        "tag":          "VAPI-VAME-v1",
        "tag_length":   12,
        "primitive":    "Application-Layer Message Envelope (transport binding)",
        "preimage":     "tag(12B) || chain_head_16b || ts_ns_be(8B) || endpoint || body",
        "output":       "SHA-256 -> 32B (response header X-VAME-Commitment)",
        "py_module":    "bridge/vapi_bridge/vame.py",
        "py_function":  "stamp_response_headers",
    },
    {
        "tag":          "VAPI-CORPUS-SNAPSHOT-v1",
        "tag_length":   23,
        "primitive":    "Wiki + agent corpus state snapshot",
        "preimage":     "tag(23B) || wiki_hash(32B) || agent_root(32B) || "
                        "ratio_milli_be(8B) || corpus_n_be(8B) || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/corpus_snapshot.py",
        "py_function":  "compute_corpus_snapshot_commitment",
    },
    {
        "tag":          "VAPI-CONSENT-v1",
        "tag_length":   15,
        "primitive":    "Per-category gamer consent commitment",
        "preimage":     "tag(15B) || device_id_b32 || category_bitmask_be(4B) "
                        "|| expires_at_be(8B) || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/consent_categories.py",
        "py_function":  "compute_consent_hash",
    },
    {
        "tag":          "VAPI-BIOMETRIC-SNAPSHOT-v1",
        "tag_length":   26,
        "primitive":    "ZK-friendly biometric snapshot commitment",
        "preimage":     "tag(26B) || feature_root(32B) || n_features_be(4B) "
                        "|| device_id_b32 || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/biometric_snapshot.py",
        "py_function":  "compute_biometric_snapshot_commitment",
    },
    {
        "tag":          "VAPI-LISTING-v1",
        "tag_length":   15,
        "primitive":    "Marketplace listing commitment",
        "preimage":     "tag(15B) || seller_b32 || sepproof_commit(32B) "
                        "|| biometric_snap(32B) || corpus_snap(32B) || gic(32B) "
                        "|| consent_bitmask_be(4B) || data_class_be(1B) || "
                        "ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/listing_primitive.py",
        "py_function":  "compute_listing_commitment",
    },
    {
        "tag":          "VAPI-FRR-v1",
        "tag_length":   11,
        "primitive":    "Fleet Readiness Root",
        "preimage":     "tag(11B) || sorted_for_each_agent[agent_id_be(32B) "
                        "|| phase_code(1B)] || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/operator_initiative_advancement.py",
        "py_function":  "compute_fleet_readiness_root",
    },
    {
        "tag":          "VAPI-ZKBA-ARTIFACT-v1",
        "tag_length":   21,
        "primitive":    "ZK-Backed Audit artifact commitment",
        "preimage":     "tag(21B) || class_byte(1B) || weight_byte(1B) || "
                        "n_components_be(1B) || sorted_component_hashes || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/zkba_artifact.py",
        "py_function":  "compute_zkba_commitment",
    },
    {
        "tag":          "VAPI-AGENT-COMMIT-v1",
        "tag_length":   20,
        "primitive":    "Operator-agent action commitment",
        "preimage":     "tag(20B) || agent_id(32B) || action_name || "
                        "payload_hash(32B) || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/agent_commit.py",
        "py_function":  "compute_agent_commit_hash",
    },
    {
        "tag":          "VAPI-PHYSICAL-DATA-ATTESTATION-v1",
        "tag_length":   33,
        "primitive":    "PDA — physical sensor attestation",
        "preimage":     "tag(33B) || device_id_b32 || sensor_feature_root(32B) "
                        "|| ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/physical_data_attestation.py",
        "py_function":  "compute_pda_commitment",
    },
    {
        "tag":          "VAPI-BT-WITNESS-v1",
        "tag_length":   18,
        "primitive":    "BR/EDR Bluetooth witness presence attestation",
        "preimage":     "tag(18B) || witness_node_id || target_bd_addr "
                        "|| rssi_samples_hash(32B) || ts_ns_be(8B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/bt_witness.py",
        "py_function":  "compute_bt_witness_commitment",
    },
    {
        "tag":          "VAPI-CEDAR-BUNDLE-v1",
        "tag_length":   20,
        "primitive":    "Cedar policy bundle Merkle root",
        "preimage":     "Merkle tree over per-policy SHA-256 leaves",
        "output":       "SHA-256 root -> 32B",
        "py_module":    "bridge/vapi_bridge/cedar_parser.py",
        "py_function":  "bundle_merkle_root",
    },
    {
        "tag":          "PoAC record body hash (NO domain tag — wire-format-bound)",
        "tag_length":   0,
        "primitive":    "PoAC record link hash (chain backbone)",
        "preimage":     "228-byte wire record bytes[0:164] (body only — NOT 228B)",
        "output":       "SHA-256 -> 32B",
        "py_module":    "bridge/vapi_bridge/codec.py",
        "py_function":  "record_hash (line 200)",
    },
]


# ---------------------------------------------------------------------------
# Sliding-window per-IP rate limiter (mirrors operator_api._RateLimiter
# pattern but lives here so the public app is self-contained).
# ---------------------------------------------------------------------------

class _PublicRateLimiter:
    def __init__(self, requests_per_minute: int = 60) -> None:
        self._rpm = max(1, int(requests_per_minute))
        self._windows: "collections.defaultdict[str, collections.deque]" = (
            collections.defaultdict(collections.deque)
        )

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - 60.0
        dq = self._windows[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= self._rpm:
            return False
        dq.append(now)
        return True


def _client_ip(request: Request) -> str:
    """Best-effort client-IP key for rate-limiting."""
    fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if fwd:
        return fwd
    return getattr(request.client, "host", "unknown") if request.client else "unknown"


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_public_forensic_app(*, cfg, store) -> FastAPI:
    """Build the public sub-app. NO auth. Rate-limit + VAME-stamp + CORS.
    Mount via app.mount('/public', create_public_forensic_app(cfg=..., store=...)).
    """
    app = FastAPI(
        title="VAPI Public Forensic Replay-and-Verify API",
        version="1.0.0-phase-o5-public-viewer",
    )

    _rpm = int(getattr(cfg, "public_forensic_rate_limit_per_min", 60))
    _limiter = _PublicRateLimiter(requests_per_minute=_rpm)

    def _check_rate(request: Request) -> None:
        key = _client_ip(request)
        if not _limiter.is_allowed(key):
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded (60 req/min/IP)",
                headers={"Retry-After": "60"},
            )

    # ----- VAME middleware (LOCKED ENABLED per plan operator-confirmation) -----
    # Stamps every JSON response with the X-VAME-* sidecar headers so external
    # auditors get the same content-vs-transport integrity guarantee operator
    # routes have. Mirrors operator_api._VAMEMiddleware exactly.
    try:
        from .vame import stamp_response_headers as _vame_stamp_headers

        _vame_cache: Dict[str, Any] = {"head": "", "expires_at": 0.0}
        _VAME_TTL_S = 5.0

        def _vame_head_hex() -> str:
            now = time.time()
            if now < _vame_cache["expires_at"] and _vame_cache["head"]:
                return _vame_cache["head"]
            try:
                sid = getattr(cfg, "grind_session_id", "") or ""
                st = store.get_grind_chain_status(sid, cfg=cfg)
                head = (st.get("latest_gic_hash") or "")[:32]
            except Exception:  # noqa: BLE001
                head = ""
            _vame_cache["head"] = head
            _vame_cache["expires_at"] = now + _VAME_TTL_S
            return head

        class _PublicVAMEMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                path = request.url.path or ""
                response = await call_next(request)
                if path.endswith("/health"):
                    return response
                ct = (response.headers.get("content-type") or "").lower()
                if "application/json" not in ct:
                    return response
                if response.status_code >= 500:
                    return response
                body_chunks: list[bytes] = []
                async for chunk in response.body_iterator:
                    body_chunks.append(chunk)
                body_bytes = b"".join(body_chunks)
                try:
                    headers = _vame_stamp_headers(
                        _vame_head_hex(), path, body_bytes,
                    )
                except Exception as e:  # noqa: BLE001
                    log.debug("public VAME stamp failed %s: %s", path, e)
                    headers = {}
                new_headers = dict(response.headers)
                new_headers.update(headers)
                if "content-length" in new_headers:
                    new_headers["content-length"] = str(len(body_bytes))
                return _StarletteResponse(
                    content=body_bytes,
                    status_code=response.status_code,
                    headers=new_headers,
                    media_type=response.media_type,
                )

        app.add_middleware(_PublicVAMEMiddleware)
    except Exception as _vame_exc:  # noqa: BLE001
        log.warning(
            "public_forensic_api: VAME middleware unavailable (%s); "
            "endpoints serve unstamped", _vame_exc,
        )

    # CORS — expose VAME headers to the browser fetch() reader.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # PUBLIC sub-app — read-only, no creds
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=[
            "X-VAME-Version", "X-VAME-Commitment", "X-VAME-Chain-Head",
            "X-VAME-TS-NS",   "X-VAME-Endpoint",
        ],
    )

    # ---------------- Route #1: /health ----------------
    @app.get("/health")
    def public_health():
        return {"status": "ok", "scope": "public", "ts": time.time()}

    # ---------------- Route #2: /algorithms ----------------
    @app.get("/algorithms")
    def public_algorithms(request: Request):
        _check_rate(request)
        return {
            "schema":    "vapi-public-algorithm-manifest-v1",
            "count":     len(_FROZEN_V1_ALGORITHMS),
            "tags":      _FROZEN_V1_ALGORITHMS,
            "discipline":(
                "Every algorithm listed here is reproducible in any browser "
                "via window.crypto.subtle.digest('SHA-256', bytes). The "
                "frontend module frontend/src/crypto/vapi_verifier.js "
                "exports a function per tag that mirrors the Python "
                "implementation byte-for-byte."
            ),
            "timestamp": time.time(),
        }

    # ---------------- Route #3: /session/{commitment_hex} ----------------
    @app.get("/session/{commitment_hex}")
    async def public_session(
        commitment_hex: str = FPath(..., min_length=1),
        request: Request = None,  # type: ignore
    ):
        _check_rate(request)
        comp = await asyncio.to_thread(
            store.get_session_composite, commitment_hex,
        )
        comp["timestamp"] = time.time()
        return comp

    # ---------------- Route #4: /vpm/{commitment_hex} ----------------
    @app.get("/vpm/{commitment_hex}")
    async def public_vpm(
        commitment_hex: str = FPath(..., min_length=1),
        request: Request = None,  # type: ignore
    ):
        _check_rate(request)
        row = await asyncio.to_thread(
            store.get_vpm_artifact_status, commitment_hex,
        )
        if row is None:
            return {
                "found":          False,
                "commitment_hex": commitment_hex,
                "timestamp":      time.time(),
            }
        return {
            "found":     True,
            "vpm":       row,
            "timestamp": time.time(),
        }

    # ---------------- Route #5: /vpm/{commitment_hex}/preimage ----------------
    @app.get("/vpm/{commitment_hex}/preimage")
    async def public_vpm_preimage(
        commitment_hex: str = FPath(..., min_length=1),
        request: Request = None,  # type: ignore
    ):
        _check_rate(request)
        row = await asyncio.to_thread(
            store.get_vpm_artifact_status, commitment_hex,
        )
        if row is None:
            return {
                "found":          False,
                "commitment_hex": commitment_hex,
                "timestamp":      time.time(),
            }
        return {
            "found":              True,
            "commitment_hex":     commitment_hex,
            "vpm_id":             row.get("vpm_id"),
            "preimage_json":      row.get("preimage_json", "{}"),
            "integrity_label_hash_hex": row.get("integrity_label_hash_hex"),
            "zkba_manifest_hash_hex":   row.get("zkba_manifest_hash_hex"),
            "wrapper_schema":     row.get("wrapper_schema"),
            "ts_ns":              row.get("ts_ns"),
            "timestamp":          time.time(),
        }

    # ---------------- Route #6: /gic/{grind_session_id} ----------------
    @app.get("/gic/{grind_session_id}")
    async def public_gic_chain(
        grind_session_id: str = FPath(..., min_length=1),
        request: Request = None,  # type: ignore
    ):
        _check_rate(request)
        status = await asyncio.to_thread(
            store.get_grind_chain_status, grind_session_id, cfg=cfg,
        )
        return {
            "grind_session_id":  grind_session_id,
            "chain_length":      status.get("chain_length", 0),
            "latest_gic_hash":   status.get("latest_gic_hash", ""),
            "chain_intact":      bool(status.get("chain_intact", False)),
            "genesis_ts":        status.get("genesis_ts", 0.0),
            "latest_ts":         status.get("latest_ts", 0.0),
            "discipline":        (
                "Re-derive each chain link by calling "
                "verifyGicChainLink(prev_gic, commitment, verdict_code, "
                "host_state_code, ts_ns) in vapi_verifier.js"
            ),
            "timestamp":         time.time(),
        }

    # ---------- Route #6b: /gic/{sid}/links — Phase O5-PUBLIC-VIEWER Stage 2 ----------
    @app.get("/gic/{grind_session_id}/links")
    async def public_gic_links(
        grind_session_id: str = FPath(..., min_length=1),
        limit: int = 200,
        offset: int = 0,
        request: Request = None,  # type: ignore
    ):
        """Return all GIC chain links for a grind session so the browser
        can recompute SHA-256 of each link via verifyGicChainLink and
        confirm the chain is intact end-to-end.

        Phase O5-PUBLIC-VIEWER Stage 2 — the GIC Chain Explorer's
        backbone. Each row carries the inputs the browser-side
        verifyGicChainLink function needs: prev_gic (=previous row's
        grind_chain_hash), commitment_hash, verdict_code (mapped from
        fallback_verdict), pcc_host_code (mapped from pcc_host_state),
        gic_ts_ns, and the protocol-side grind_chain_hash to compare
        against.

        Rate-limited; no auth; PII-safe (all fields are protocol-public).
        """
        _check_rate(request)
        # Verdict + host-state code tables — frozen mirrors of grind_chain.py
        verdict_codes = {
            "CLEAR": 0x00, "CERTIFY": 0x01, "FLAG": 0x10,
            "HOLD": 0x11, "BLOCK": 0x20,
        }
        host_codes = {
            "EXCLUSIVE_USB": 0x01, "UNKNOWN": 0x02, "EXCLUSIVE_BT": 0x10,
            "CONTESTED": 0x20, "DEGRADED": 0x30, "DISCONNECTED": 0xFF,
        }
        rows = await asyncio.to_thread(
            store.get_gic_chain_links,
            grind_session_id, int(limit), int(offset),
        )
        # Compute prev_gic per row (the previous row's grind_chain_hash;
        # first row gets "" so the browser knows to compute genesis_gic)
        links = []
        prev = ""
        for r in rows:
            d = dict(r)
            d["prev_gic_hex"] = prev
            d["verdict_code"] = verdict_codes.get(
                str(d.get("fallback_verdict") or "FLAG"),
                verdict_codes["FLAG"],
            )
            d["host_state_code"] = host_codes.get(
                str(d.get("pcc_host_state") or "DISCONNECTED"),
                host_codes["DISCONNECTED"],
            )
            links.append(d)
            prev = str(d.get("grind_chain_hash") or "")
        return {
            "schema":            "vapi-public-gic-chain-links-v1",
            "grind_session_id":  grind_session_id,
            "chain_length":      len(links),
            "links":             links,
            "discipline":        (
                "For each link i, recompute via "
                "verifyGicChainLink(prev_gic_hex, commitment_hash, "
                "verdict_code, host_state_code, gic_ts_ns) and confirm "
                "the result equals grind_chain_hash. For link [0], also "
                "call verifyGicGenesis(grind_session_id, gic_ts_ns) to "
                "anchor the chain to the FROZEN-v1 genesis tag "
                "b'VAPI-GIC-GENESIS-v1'."
            ),
            "timestamp":         time.time(),
        }

    # ---------------- Route #7: /mlga/{dataproof_hex} ----------------
    @app.get("/mlga/{dataproof_hex}")
    async def public_mlga(
        dataproof_hex: str = FPath(..., min_length=64, max_length=66),
        request: Request = None,  # type: ignore
    ):
        _check_rate(request)
        h = (dataproof_hex or "").lower().removeprefix("0x")
        if len(h) != 64:
            return {
                "found":         False,
                "dataproof_hex": dataproof_hex,
                "reason":        "invalid dataproof_hex length",
                "timestamp":     time.time(),
            }
        # Fetch MLGA row by dataproof_hex via direct SQLite read on the
        # store's connection. Read-only; safe.
        try:
            import sqlite3 as _sql
            db_path = getattr(store, "_db_path", None) or getattr(
                store, "db_path", None
            )
            if not db_path:
                return {
                    "found":         False,
                    "dataproof_hex": h,
                    "reason":        "store unavailable",
                    "timestamp":     time.time(),
                }
            con = _sql.connect(db_path, timeout=2.0)
            try:
                con.row_factory = _sql.Row
                row = con.execute(
                    "SELECT id, session_id, session_start_ts_ns, "
                    "       session_end_ts_ns, n_poac_records, "
                    "       n_trigger_pulls_r2, n_trigger_pulls_l2, "
                    "       apop_state_counts_json, bt_observability, "
                    "       gic_advances_in_session, dataproof_hex "
                    "FROM mlga_session_log WHERE dataproof_hex = ?",
                    (h,),
                ).fetchone()
            finally:
                con.close()
            if row is None:
                return {
                    "found":         False,
                    "dataproof_hex": h,
                    "timestamp":     time.time(),
                }
            d = dict(row)
            return {
                "found":      True,
                "mlga":       d,
                "preimage_components": {
                    "domain_tag":                 "VAPI-MLGA-SESSION-v1",
                    "start_ts_ns":                d["session_start_ts_ns"],
                    "end_ts_ns":                  d["session_end_ts_ns"],
                    "n_poac_records":             d["n_poac_records"],
                    "n_trigger_pulls_r2":         d["n_trigger_pulls_r2"],
                    "n_trigger_pulls_l2":         d["n_trigger_pulls_l2"],
                    "apop_state_counts_json":     d["apop_state_counts_json"],
                    "bt_observability":           d["bt_observability"],
                    "gic_advances_in_session":    d["gic_advances_in_session"],
                },
                "timestamp":  time.time(),
            }
        except Exception as exc:  # noqa: BLE001
            log.warning("public /mlga error: %s", exc)
            return {
                "found":         False,
                "dataproof_hex": h,
                "reason":        "internal_lookup_error",
                "timestamp":     time.time(),
            }

    # ---------------- Route #8: /record/{device_id}/{counter} ----------------
    @app.get("/record/{device_id}/{counter}")
    async def public_record(
        device_id: str,
        counter: int,
        request: Request,
    ):
        _check_rate(request)
        raw = await asyncio.to_thread(
            store.get_record_raw_bytes, device_id, int(counter),
        )
        if raw is None:
            raise HTTPException(
                404, f"record not found: device={device_id} counter={counter}",
            )
        return _StarletteResponse(
            content=raw,
            media_type="application/octet-stream",
            headers={
                "Cache-Control":      "public, max-age=300",
                "X-VAPI-Wire-Length": "228",
                "X-VAPI-Hash-Algo":   "SHA-256(raw[:164])",
                "Content-Length":     "228",
            },
        )

    # ---------------- Route #9: /agent-roots ----------------
    @app.get("/agent-roots")
    def public_agent_roots(request: Request):
        _check_rate(request)
        return {
            "schema": "vapi-public-agent-roots-v1",
            "agents": [
                {
                    "canonical":  "anchor_sentry",
                    "agent_id":   getattr(cfg, "operator_agent_sentry_id", ""),
                    "phase":      "O1_SHADOW",
                    "ioid_did":   "did:io:eaA6FD569a964C08D541F8e154aB3Ac8cD4e2743",
                    "tba":        "0xCc59C57bB7746791Be0945BfB96Be408a73944e4",
                    "cedar_bundle_merkle":
                        "0xebe899279b230ff5d71db22dc4b80282c810ff5bd1a9d249db6e6d309af52e41",
                },
                {
                    "canonical":  "guardian",
                    "agent_id":   getattr(cfg, "operator_agent_guardian_id", ""),
                    "phase":      "O1_SHADOW",
                    "ioid_did":   "did:io:9c577fb2162824565ef57edd1b55a8ec5f58c181",
                    "tba":        "0xd7aDA37AdFC08Fed43c934aB3b9609697b739092",
                    "cedar_bundle_merkle":
                        "0x46807e13dd1c81cefa784ab8b30f8cdcaefd60697de921aae46ac24dac000a50",
                },
                {
                    "canonical":  "curator",
                    "agent_id":   getattr(cfg, "operator_agent_curator_id", ""),
                    "phase":      "O1_SHADOW",
                    "ioid_did":   "did:io:0x7BdB744c87c8f86e348246557BB58D60641312C2",
                    "tba":        "0x6A385dF2501D42ef2Cf918eE1e3b6011903e418F",
                    "cedar_bundle_merkle":
                        "0x44f89d0a05e7594741f7a06a1c4ca817d58396ad41b22b0eb5d0b5ce4be88ae6",
                },
            ],
            "discipline":(
                "Each agent's identity is on-chain in IoTeX AgentRegistry + "
                "AgentScope. Cedar bundle Merkles are independently "
                "verifiable via the cedar_bundle_validate.py CLI; the "
                "browser-side verifyCedarBundleMerkle() function in "
                "vapi_verifier.js mirrors the bundle_merkle_root algorithm."
            ),
            "chain": {
                "name":      "IoTeX",
                "chain_id":  4690,
                "network":   "testnet",
            },
            "timestamp": time.time(),
        }

    # ---------------- Route #10: /protocol-state ----------------
    @app.get("/protocol-state")
    async def public_protocol_state(request: Request):
        _check_rate(request)
        snap = await asyncio.to_thread(store.get_protocol_state_snapshot)
        snap["schema"] = "vapi-public-protocol-state-v1"
        return snap

    return app
