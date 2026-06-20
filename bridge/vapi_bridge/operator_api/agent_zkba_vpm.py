"""ZKBA + VPM artifact routes (D-DECON-2 operator_api residue #12).

Register-function split per audits/decon-store-map.md agent_zkba_vpm domain.
Routes byte-identical to the former inline handlers in _app.py.
"""
from __future__ import annotations

import asyncio
import hmac
import time
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Header, HTTPException, Query, Request

# FROZEN CSP header set for VPM HTML responses (INV-VPM-CSP-001)
_VPM_HTML_RESPONSE_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; "
        "style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; "
        "img-src data:; "
        "base-uri 'none'; "
        "frame-ancestors 'self'; "
        "form-action 'none'"
    ),
    "Referrer-Policy":         "no-referrer",
    "X-Content-Type-Options":  "nosniff",
    "X-Frame-Options":         "SAMEORIGIN",
    "Cache-Control":           "public, max-age=31536000, immutable",
}

_VPM_COMPILER_REGISTRY = {
    "HONESTY-BOARD-v1":   ("vpm_compile_honesty_board",   "build_honesty_board_artifact"),
    "AGENT-REVIEW-v1":    ("vpm_compile_agent_review",    "build_agent_review_artifact"),
    "CDRR-DAG-v1":        ("vpm_compile_cdrr_dag",        "build_cdrr_dag_artifact"),
    "GIC-LEDGER-BETA-v1": ("vpm_compile_gic_ledger_beta", "build_gic_ledger_beta_artifact"),
    "DISPUTE-PACKET-v1":  ("vpm_compile_dispute_packet",  "build_dispute_packet_artifact"),
    "MARKET-LISTING-v1":  ("vpm_compile_market_listing",  "build_market_listing_artifact"),
}

_VPM_VALID_VISUAL_STATES = frozenset((
    "live", "dry-run", "emulated", "frozen-disabled", "revoked", "unverified",
))
_VPM_VALID_CAPTURE_MODES = frozenset((
    "live", "dry-run", "emulated", "demo", "frozen-disabled",
))


def register_agent_zkba_vpm_routes(
    app: FastAPI,
    *,
    cfg,
    store,
    check_read_key: Callable[[str], None],
    repo_root: Path,
    bridge_dir: Path,
) -> None:
    """Register ZKBA read/validate and VPM compile/list/audit routes."""

    # ------------------------------------------------------------------
    # Phase O3-ZKBA-TRACK1 (post-C5) — VAPIZKBA bridge HTTP endpoints.
    #
    # Three read-only GETs that close the wire-contract loop with the
    # VAPIZKBA SDK class shipped at C4 (sdk/vapi_sdk.py:9170+). At C4
    # commit time the SDK was wire-locked against future endpoints; this
    # block ships those endpoints.
    #
    # Track 1 invariant: anchor_tx_hash IS NULL across all rows (Stream A3
    # will populate it post-§8 gate). The /operator/zkba-status response
    # surfaces track1_invariant_holds = (anchored_count == 0) so external
    # tooling can verify the invariant without re-scanning the table.
    #
    # No Cedar evaluation, no operator-agent draft emission, no chain
    # call — pure read-only wrappers over store.get_zkba_artifact_*
    # helpers. Wallet impact 0 IOTX.
    # ------------------------------------------------------------------
    @app.get("/operator/zkba-status")
    async def get_zkba_status(
        x_api_key: str = Header(default=""),
    ):
        """Phase O3-ZKBA-TRACK1 — aggregate status over zkba_artifact_log.

        Returns the shape consumed by VAPIZKBA.status() at
        sdk/vapi_sdk.py:9260-9285:

            {
                "total_artifacts":        int,
                "anchored_count":         int,
                "track1_invariant_holds": bool,
                "class_breakdown":        {zkba_class_int: count, ...},
                "latest": {
                    "commitment_hex": str,
                    "zkba_class":     int,
                    "proof_weight":   int,
                    "ts_ns":          int,
                },
                "frozen_v1_position": 10,
                "domain_tag":         "VAPI-ZKBA-ARTIFACT-v1",
                "timestamp":          float,
            }

        Read-key auth. Fail-open at the store layer.
        """
        check_read_key(x_api_key)
        summary = await asyncio.to_thread(store.get_zkba_artifact_summary)
        latest_raw = summary.get("latest")
        if latest_raw is None:
            latest_out: dict = {}
        else:
            latest_out = {
                "commitment_hex": str(latest_raw.get("commitment_hex", "")),
                "zkba_class":     int(latest_raw.get("zkba_class", 0)),
                "proof_weight":   int(latest_raw.get("proof_weight", 0)),
                "ts_ns":          int(latest_raw.get("ts_ns", 0)),
            }
        return {
            "total_artifacts":        int(summary.get("total_artifacts", 0)),
            "anchored_count":         int(summary.get("anchored_count", 0)),
            "track1_invariant_holds": bool(summary.get("track1_invariant_holds", True)),
            "class_breakdown":        dict(summary.get("class_breakdown", {})),
            "latest":                 latest_out,
            "frozen_v1_position":     10,
            "domain_tag":             "VAPI-ZKBA-ARTIFACT-v1",
            "timestamp":              time.time(),
        }

    @app.get("/operator/zkba-artifact/{commitment_hex}")
    async def get_zkba_artifact_endpoint(
        commitment_hex: str,
        x_api_key: str = Header(default=""),
    ):
        """Phase O3-ZKBA-TRACK1 — fetch one ZKBA artifact row by commitment_hex.

        Returns the shape consumed by VAPIZKBA.get_artifact() at
        sdk/vapi_sdk.py:9287-9315:

            {"found": false, "commitment_hex": str}                          # miss
            {"found": true,  "db_row": {... full row ...}}                   # hit

        Read-key auth. Returns 200 + found=False on miss (NOT 404) — the
        SDK consumes the boolean rather than parsing HTTP status, and
        404s would force callers into exception-handling code paths.
        """
        check_read_key(x_api_key)
        row = await asyncio.to_thread(
            store.get_zkba_artifact_status, commitment_hex
        )
        if row is None:
            return {
                "found":          False,
                "commitment_hex": commitment_hex,
                "timestamp":      time.time(),
            }
        return {
            "found":          True,
            "commitment_hex": commitment_hex,
            "db_row":         row,
            "timestamp":      time.time(),
        }

    @app.get("/operator/zkba-history")
    async def get_zkba_history_endpoint(
        x_api_key: str = Header(default=""),
        limit: int = Query(default=20, ge=1, le=500),
    ):
        """Phase O3-ZKBA-TRACK1 — paginated DESC-by-ts_ns ZKBA artifact history.

        Returns the shape consumed by VAPIZKBA.history() at
        sdk/vapi_sdk.py:9317-9338:

            {
                "limit":     int,
                "row_count": int,
                "rows":      [dict, ...],   # newest first
                "timestamp": float,
            }

        Read-key auth. limit clamped 1..500 by Query bounds.
        """
        check_read_key(x_api_key)
        rows = await asyncio.to_thread(
            store.get_zkba_artifact_history, int(limit)
        )
        return {
            "limit":     int(limit),
            "row_count": len(rows),
            "rows":      rows,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # Phase O3-ZKBA-TRACK1 Lane B G4 follow-up (2026-05-12) —
    # POST /operator/zkba-validate-manifest endpoint.
    #
    # Extends the G4 manifest validator's reach to the bridge HTTP
    # surface. Mirrors the C4 → c2510883 architectural pattern for the
    # ZKBA primitive itself (C4 shipped MCP + SDK wire-locked; c2510883
    # shipped the bridge endpoints closing the wire-contract loop).
    #
    # Read-only validation; no Cedar evaluation, no chain action, no
    # operator-agent draft emission, no store mutation. Wallet 0 IOTX.
    #
    # The validator module lives at scripts/zkba_manifest_validator.py
    # (alongside vsd_ui_compiler.py per G4 architectural decision). The
    # bridge does not normally import from scripts/; we do a localized
    # sys.path.insert + lazy import inside the endpoint to localize the
    # cross-directory dependency. This is a one-time inversion of the
    # usual scripts/-depends-on-bridge/ direction; it's deliberate at
    # this endpoint and not generalized.
    # ------------------------------------------------------------------
    @app.post("/operator/zkba-validate-manifest")
    async def validate_zkba_manifest_endpoint(
        request: Request,
        x_api_key: str = Header(default=""),
    ):
        """Phase O3-ZKBA-TRACK1 Lane B G4 follow-up — validate a ZKBA
        projection manifest dict against B.8 G4 rules.

        Accepts JSON body containing a manifest dict (the 8-field FROZEN
        simple-form manifest emitted by scripts/vsd_ui_compiler.compile_artifact,
        or a richer dict that includes the 8 required fields).

        Returns the same shape consumed by the MCP tool
        vapi_validate_zkba_manifest at vapi-mcp/knowledge_server.py:

            {
                "valid":             bool,
                "errors":            list[str],
                "zkba_class_name":   str,
                "proof_weight_name": str,
                "schema_name_form":  str,   # "implementation" /
                                            # "spec_design_time" /
                                            # "unknown" / "absent"
                "timestamp":         float,
            }

        Read-key auth (x-api-key Header). 422 on non-JSON or non-object
        body; 500 if validator import fails (should never happen in
        well-formed repo); validator itself is fail-open (never raises;
        malformed manifests produce valid=False + populated errors).

        Track 1 contract: the endpoint is purely a deterministic validator
        wrapper. No filesystem writes, no DB inserts, no chain reads.
        """
        check_read_key(x_api_key)

        # Parse JSON body
        try:
            manifest = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"invalid JSON body: {exc}",
            )
        if not isinstance(manifest, dict):
            raise HTTPException(
                status_code=422,
                detail=f"body must be a JSON object; got {type(manifest).__name__}",
            )

        # Lazy import of validator. scripts/ is not on bridge's default
        # sys.path; localize the path addition here so it doesn't
        # generalize across the codebase.
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_dir = str(repo_root / "scripts")
        if _scripts_dir not in _sys.path:
            _sys.path.insert(0, _scripts_dir)
        try:
            from zkba_manifest_validator import validate_zkba_manifest  # type: ignore
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"validator import failed: {exc}",
            )

        # Run the validator (fail-open; never raises)
        result = validate_zkba_manifest(manifest)
        return {
            "valid":             bool(result.valid),
            "errors":            list(result.errors),
            "zkba_class_name":   result.zkba_class_name,
            "proof_weight_name": result.proof_weight_name,
            "schema_name_form":  result.schema_name_form,
            "timestamp":         time.time(),
        }

    # ------------------------------------------------------------------
    # Phase O4-VPM-INT Stream B (Bridge Endpoints) — VPM artifact registry
    # HTTP surface. Five new endpoints serve the read + future write +
    # validate + audit paths over scripts/vpm_compile_*.py emitted output.
    #
    #   B.1  GET  /operator/vpm-list                        (read-key)
    #   B.2  GET  /operator/vpm-artifact/{commit}           (read-key)
    #   B.3  GET  /operator/vpm-manifest/{commit}           (read-key)
    #   B.4  POST /operator/vpm-compile                     (full operator key)
    #   B.5  POST /operator/vpm-validate-manifest           (read-key)
    #   B.6  GET  /operator/vpm-audit-status                (read-key)
    #
    # This block ships B.1-B.3 (read endpoints + store-backed list). B.4-B.7
    # ship in the next plan-row commit.
    # ------------------------------------------------------------------

    @app.get("/operator/vpm-list")
    async def get_vpm_list_endpoint(
        x_api_key: str = Header(default=""),
        vpm_id: str = Query(default=""),
        visual_state: str = Query(default=""),
        since_minutes: int = Query(default=0, ge=0, le=43200),
        limit: int = Query(default=50, ge=1, le=500),
    ):
        """Phase O4-VPM-INT B.1 — list VPM artifacts from vpm_artifact_log.

        Filterable by vpm_id (e.g. HONESTY-BOARD-v1), visual_state (1-of-6
        FROZEN VPMVisualState), since_minutes (rolling time window;
        0=unbounded, max 30 days = 43200 minutes), limit (1..500).

        Returns:
            {
                "filter_summary": {"vpm_id": str, "visual_state": str,
                                   "since_minutes": int, "limit": int},
                "row_count": int,
                "rows": [{full row dict}, ...],   # newest first
                "timestamp": float,
            }

        Read-key auth (x-api-key Header). Fail-open at store layer.
        """
        check_read_key(x_api_key)
        rows = await asyncio.to_thread(
            store.get_vpm_artifact_history,
            vpm_id if vpm_id else None,
            visual_state if visual_state else None,
            int(since_minutes),
            int(limit),
        )
        return {
            "filter_summary": {
                "vpm_id":        vpm_id,
                "visual_state":  visual_state,
                "since_minutes": int(since_minutes),
                "limit":         int(limit),
            },
            "row_count": len(rows),
            "rows":      rows,
            "timestamp": time.time(),
        }

    @app.get("/operator/vpm-artifact/{commitment_hex}")
    async def get_vpm_artifact_endpoint(
        commitment_hex: str,
        x_api_key: str = Header(default=""),
    ):
        """Phase O4-VPM-INT B.2 — serve a VPM artifact's compiled HTML.

        Looks up the row in vpm_artifact_log; reads manifest_uri-pointed
        HTML file from disk; returns it with the FROZEN CSP + security
        header set per Phase O4 plan §3 Stream B.2.

        Returns:
          - 200 + HTML body + CSP headers when artifact found + file exists
          - 200 + JSON {"found": false, ...} when row missing (NOT 404)
          - 200 + JSON {"found": true, "file_missing": true, ...} when row
            present but manifest_uri file is gone from disk (operator can
            see the inconsistency without 5xx)

        Read-key auth (x-api-key Header).
        """
        check_read_key(x_api_key)
        row = await asyncio.to_thread(
            store.get_vpm_artifact_status, commitment_hex
        )
        if row is None:
            return {
                "found":          False,
                "commitment_hex": commitment_hex,
                "timestamp":      time.time(),
            }
        manifest_uri = row.get("manifest_uri")
        if not manifest_uri:
            return {
                "found":          True,
                "file_missing":   True,
                "commitment_hex": commitment_hex,
                "reason":         "no manifest_uri recorded in store row",
                "timestamp":      time.time(),
            }
        from pathlib import Path as _Path
        artifact_path = _Path(manifest_uri)
        if not artifact_path.exists():
            return {
                "found":          True,
                "file_missing":   True,
                "commitment_hex": commitment_hex,
                "manifest_uri":   manifest_uri,
                "reason":         "manifest_uri file missing from disk",
                "timestamp":      time.time(),
            }
        try:
            html_bytes = await asyncio.to_thread(artifact_path.read_bytes)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"failed to read artifact file: {exc}",
            )
        from starlette.responses import Response as _Resp
        return _Resp(
            content=html_bytes,
            media_type="text/html; charset=utf-8",
            headers=_VPM_HTML_RESPONSE_HEADERS,
        )

    @app.get("/operator/vpm-manifest/{commitment_hex}")
    async def get_vpm_manifest_endpoint(
        commitment_hex: str,
        x_api_key: str = Header(default=""),
    ):
        """Phase O4-VPM-INT B.3 — return the .vpm.manifest.json sidecar
        contents for a recorded VPM artifact.

        Derives the sidecar path from manifest_uri by replacing the
        `.html` suffix with `.vpm.manifest.json` (matches the
        compile_vpm_artifact convention at
        scripts/vsd_ui_compiler.py:compile_vpm_artifact, where both
        files are written to the same output_dir with the same
        <input_commit> stem).

        Returns:
            {
                "found":          bool,
                "commitment_hex": str,
                "manifest":       dict | None,   # parsed JSON sidecar
                "db_row":         dict | None,   # store row metadata
                "file_missing":   bool,           # true when row present
                                                  # but sidecar absent
                "timestamp":      float,
            }

        Read-key auth.
        """
        check_read_key(x_api_key)
        row = await asyncio.to_thread(
            store.get_vpm_artifact_status, commitment_hex
        )
        if row is None:
            return {
                "found":          False,
                "commitment_hex": commitment_hex,
                "manifest":       None,
                "db_row":         None,
                "file_missing":   False,
                "timestamp":      time.time(),
            }
        manifest_uri = row.get("manifest_uri")
        if not manifest_uri:
            return {
                "found":          True,
                "commitment_hex": commitment_hex,
                "manifest":       None,
                "db_row":         row,
                "file_missing":   True,
                "reason":         "no manifest_uri recorded in store row",
                "timestamp":      time.time(),
            }
        from pathlib import Path as _Path
        artifact_path = _Path(manifest_uri)
        # Derive sidecar: replace .html with .vpm.manifest.json
        if artifact_path.suffix.lower() == ".html":
            sidecar_path = artifact_path.with_name(
                artifact_path.stem + ".vpm.manifest.json"
            )
        else:
            return {
                "found":          True,
                "commitment_hex": commitment_hex,
                "manifest":       None,
                "db_row":         row,
                "file_missing":   True,
                "reason":         f"manifest_uri unexpected suffix: {artifact_path.suffix!r}",
                "timestamp":      time.time(),
            }
        if not sidecar_path.exists():
            return {
                "found":          True,
                "commitment_hex": commitment_hex,
                "manifest":       None,
                "db_row":         row,
                "file_missing":   True,
                "reason":         f"sidecar missing at {sidecar_path}",
                "timestamp":      time.time(),
            }
        try:
            sidecar_bytes = await asyncio.to_thread(sidecar_path.read_bytes)
            import json as _json
            sidecar = _json.loads(sidecar_bytes.decode("utf-8"))
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"failed to read/parse sidecar: {exc}",
            )
        return {
            "found":          True,
            "commitment_hex": commitment_hex,
            "manifest":       sidecar,
            "db_row":         row,
            "file_missing":   False,
            "timestamp":      time.time(),
        }

    # ------------------------------------------------------------------
    # Phase O4-VPM-INT Stream B Commit 2 — write + validate + audit + B.7
    # ------------------------------------------------------------------

    @app.post("/operator/vpm-compile")
    async def post_vpm_compile_endpoint(
        request: Request,
        api_key: str = Query(default=""),
    ):
        """Phase O4-VPM-INT B.4 — compile a VPM artifact + record in store.

        Full operator authority required (api_key query param matches
        cfg.operator_api_key — Phase O3 ZKBA write-endpoint convention
        at /operator/anchor-cedar-bundle and /operator/gic-reset).

        Body shape (JSON):
            {
                "vpm_id":     str (1-of-6 from _VPM_COMPILER_REGISTRY),
                "inputs":     dict (compiler-specific kwargs),
                "output_dir": str (optional; defaults to caller-supplied
                               path or frontend/src/artifacts/<id>/).
            }

        The dispatch chooses the compiler from _VPM_COMPILER_REGISTRY,
        invokes its build_*_artifact function with **inputs unpacking
        + output_dir, records the resulting row in vpm_artifact_log, and
        returns the commitment + manifest hash + row id.

        Returns:
            {
                "success":              bool,
                "vpm_id":               str,
                "input_commitment_hex": str,
                "output_hash_hex":      str,
                "output_path":          str,
                "row_id":               int (>0 on insert success;
                                             0 on UNIQUE collision
                                             returning existing id),
                "timestamp":            float,
            }

        Errors:
          403 wrong/missing api_key
          422 missing/invalid body / unknown vpm_id / invalid inputs
              (raised from compiler-side ValueError or TypeError)
          500 compiler import / runtime failure
        """
        # Full operator authority (not read-key) — mirrors anchor-cedar-bundle
        if not cfg.operator_api_key:
            raise HTTPException(503, "operator_api_key not configured")
        if not hmac.compare_digest(api_key, cfg.operator_api_key):
            raise HTTPException(403, "Invalid api_key query param")

        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"invalid JSON body: {exc}",
            )
        if not isinstance(body, dict):
            raise HTTPException(
                status_code=422,
                detail=f"body must be JSON object; got {type(body).__name__}",
            )

        vpm_id = body.get("vpm_id")
        if not isinstance(vpm_id, str) or vpm_id not in _VPM_COMPILER_REGISTRY:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"vpm_id must be one of "
                    f"{sorted(_VPM_COMPILER_REGISTRY.keys())}; got {vpm_id!r}"
                ),
            )

        inputs = body.get("inputs")
        if not isinstance(inputs, dict):
            raise HTTPException(
                status_code=422,
                detail=f"body['inputs'] must be dict; got {type(inputs).__name__}",
            )

        # Lazy import: scripts/ is not on bridge sys.path; localize the path
        # addition here (mirrors the validator endpoint pattern at
        # /operator/zkba-validate-manifest). _Path is needed before
        # output_dir resolution since that defaults to repo-root-relative.
        import sys as _sys
        from pathlib import Path as _Path

        output_dir_str = body.get("output_dir")
        if output_dir_str is None:
            output_dir_str = str(
                repo_root
                / "frontend" / "src" / "artifacts"
                / vpm_id.lower().replace("-v1", "").replace("-", "_")
            )

        _scripts_dir = str(repo_root / "scripts")
        if _scripts_dir not in _sys.path:
            _sys.path.insert(0, _scripts_dir)
        # bridge/ must also be on path for compiler imports of vapi_bridge.*
        _bridge_dir = str(bridge_dir)
        if _bridge_dir not in _sys.path:
            _sys.path.insert(0, _bridge_dir)

        module_name, fn_name = _VPM_COMPILER_REGISTRY[vpm_id]
        try:
            import importlib
            mod = importlib.import_module(module_name)
            build_fn = getattr(mod, fn_name)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"compiler import failed: {exc}",
            )

        # Build the artifact + record the store row in a worker thread.
        # compile_vpm_artifact + build_*_artifact + store insert all do
        # synchronous filesystem + DB work; asyncio.to_thread keeps the
        # event loop responsive for concurrent /vpm-list reads.
        def _build_and_record():
            manifest = build_fn(
                output_dir=_Path(output_dir_str),
                **inputs,
            )
            row_id = store.insert_vpm_artifact(
                commitment_hex=manifest.input_commitment_hex,
                vpm_id=manifest.vpm_id,
                zkba_class=manifest.zkba_class,
                proof_weight=manifest.proof_weight,
                visual_state=manifest.visual_state,
                capture_mode=manifest.capture_mode,
                integrity_label_hash_hex=manifest.integrity_label_hash_hex,
                wrapper_schema=manifest.wrapper_schema,
                zkba_manifest_hash_hex=manifest.zkba_manifest_hash_hex,
                manifest_uri=manifest.output_path,
                compiler_output_hash_hex=manifest.output_hash_hex,
                preimage_json="{}",
                ts_ns=manifest.ts_ns,
            )
            return manifest, row_id

        try:
            manifest, row_id = await asyncio.to_thread(_build_and_record)
        except (ValueError, TypeError) as exc:
            # Compiler input validation failure
            raise HTTPException(
                status_code=422,
                detail=f"compiler rejected inputs: {exc}",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"compiler runtime failure: {exc}",
            )

        return {
            "success":              True,
            "vpm_id":               manifest.vpm_id,
            "input_commitment_hex": manifest.input_commitment_hex,
            "output_hash_hex":      manifest.output_hash_hex,
            "output_path":          manifest.output_path,
            "row_id":               int(row_id),
            "timestamp":            time.time(),
        }

    @app.post("/operator/vpm-validate-manifest")
    async def post_vpm_validate_manifest_endpoint(
        request: Request,
        x_api_key: str = Header(default=""),
    ):
        """Phase O4-VPM-INT B.5 — validate a VPM artifact manifest dict.

        Validates the .vpm.manifest.json sidecar shape emitted by
        scripts/vsd_ui_compiler.compile_vpm_artifact() — schema string,
        zkba_class enum range (1..7), proof_weight enum range (1..6),
        visual_state FROZEN 6-element set, capture_mode FROZEN 5-element
        set, integrity_label_hash_hex shape (64 lowercase hex),
        wrapper_schema reference shape, zkba_manifest_hash_hex shape.

        Read-key auth. Fail-open: malformed manifests produce
        valid=False with populated errors list; the validator never
        raises HTTPException for content issues.

        Returns:
            {
                "valid":                  bool,
                "errors":                 list[str],
                "schema_recognized":      bool,    # schema == vapi-vpm-artifact-v1
                "visual_state_recognized": bool,
                "capture_mode_recognized": bool,
                "vpm_id_in_body":         str,     # for cross-ref
                "timestamp":              float,
            }
        """
        check_read_key(x_api_key)

        try:
            manifest = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"invalid JSON body: {exc}",
            )
        if not isinstance(manifest, dict):
            raise HTTPException(
                status_code=422,
                detail=f"body must be JSON object; got {type(manifest).__name__}",
            )

        errors: list[str] = []
        # Schema
        schema = manifest.get("schema")
        schema_recognized = schema == "vapi-vpm-artifact-v1"
        if not schema_recognized:
            errors.append(
                f"schema must be 'vapi-vpm-artifact-v1'; got {schema!r}"
            )

        # zkba_class
        zkba_class = manifest.get("zkba_class")
        if not isinstance(zkba_class, int) or zkba_class < 1 or zkba_class > 7:
            errors.append(
                f"zkba_class must be int in 1..7; got {zkba_class!r}"
            )

        # proof_weight
        proof_weight = manifest.get("proof_weight")
        if not isinstance(proof_weight, int) or proof_weight < 1 or proof_weight > 6:
            errors.append(
                f"proof_weight must be int in 1..6; got {proof_weight!r}"
            )

        # visual_state
        visual_state = manifest.get("visual_state")
        visual_state_recognized = visual_state in _VPM_VALID_VISUAL_STATES
        if not visual_state_recognized:
            errors.append(
                f"visual_state must be one of {sorted(_VPM_VALID_VISUAL_STATES)}; "
                f"got {visual_state!r}"
            )

        # capture_mode
        capture_mode = manifest.get("capture_mode")
        capture_mode_recognized = capture_mode in _VPM_VALID_CAPTURE_MODES
        if not capture_mode_recognized:
            errors.append(
                f"capture_mode must be one of {sorted(_VPM_VALID_CAPTURE_MODES)}; "
                f"got {capture_mode!r}"
            )

        # integrity_label_hash_hex
        ilh = manifest.get("integrity_label_hash_hex")
        if not isinstance(ilh, str) or len(ilh) != 64:
            errors.append(
                f"integrity_label_hash_hex must be 64-char hex; got "
                f"{len(ilh) if isinstance(ilh, str) else type(ilh).__name__}"
            )
        else:
            try:
                int(ilh, 16)
            except ValueError:
                errors.append("integrity_label_hash_hex not valid hex")

        # wrapper_schema
        wrapper_schema = manifest.get("wrapper_schema")
        if wrapper_schema != "vapi-vpm-manifest-v1":
            errors.append(
                f"wrapper_schema must be 'vapi-vpm-manifest-v1'; got {wrapper_schema!r}"
            )

        # zkba_manifest_hash_hex
        zmh = manifest.get("zkba_manifest_hash_hex")
        if not isinstance(zmh, str) or len(zmh) != 64:
            errors.append(
                f"zkba_manifest_hash_hex must be 64-char hex; got "
                f"{len(zmh) if isinstance(zmh, str) else type(zmh).__name__}"
            )
        else:
            try:
                int(zmh, 16)
            except ValueError:
                errors.append("zkba_manifest_hash_hex not valid hex")

        # vpm_id required + non-empty (no enum check at endpoint —
        # internal IDs like CDRR-DAG-v1 are accepted)
        vpm_id_in = manifest.get("vpm_id")
        if not isinstance(vpm_id_in, str) or not vpm_id_in:
            errors.append(
                f"vpm_id must be non-empty str; got {vpm_id_in!r}"
            )

        return {
            "valid":                   len(errors) == 0,
            "errors":                  errors,
            "schema_recognized":       schema_recognized,
            "visual_state_recognized": visual_state_recognized,
            "capture_mode_recognized": capture_mode_recognized,
            "vpm_id_in_body":          str(vpm_id_in) if isinstance(vpm_id_in, str) else "",
            "timestamp":               time.time(),
        }

    @app.get("/operator/vpm-audit-status")
    async def get_vpm_audit_status_endpoint(
        x_api_key: str = Header(default=""),
    ):
        """Phase O4-VPM-INT B.6 — run the scripts/vpm_audit.py harness
        programmatically + return the audit report JSON.

        Reuses the same audit script that ships at scripts/vpm_audit.py
        per Phase O4 plan section 3 Stream A.4 — surfaces the 6-section
        audit (active compiler registry / draft manifests / section 10
        ladder / CFSS lane assignment / source discipline / visual
        grammar coverage) at HTTP for the Operator Console.

        Read-key auth. The audit is wallet-free + read-only.

        Returns the run_audit() output dict shape directly: see
        scripts/vpm_audit.py:run_audit() docstring.
        """
        check_read_key(x_api_key)

        # Lazy import of audit script
        import sys as _sys
        from pathlib import Path as _Path
        _scripts_dir = str(repo_root / "scripts")
        if _scripts_dir not in _sys.path:
            _sys.path.insert(0, _scripts_dir)
        try:
            from vpm_audit import run_audit  # type: ignore
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"vpm_audit import failed: {exc}",
            )

        # Audit walks filesystem; offload to worker thread to keep loop responsive
        report = await asyncio.to_thread(run_audit, repo_root)
        report["timestamp"] = time.time()
        return report
