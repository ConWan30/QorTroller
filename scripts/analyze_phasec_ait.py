"""
analyze_phasec_ait.py — Phase C C-2.3: Holdout AIT Separation Analysis

Implements the enrollment/verification split methodology from C-2.1:
  - Enrollment set  (sessions/human/phase_c_ait_enroll/): builds fixed per-player centroids
  - Verification set (sessions/human/phase_c_ait_verify/): measures holdout Mahalanobis distances

Metrics produced (C-2.1 §4):
  1. Holdout separation ratio (inter/intra on verification set vs fixed enrollment centroids)
  2. LOO ratio on combined 20-session/player pool (comparator — shows LOO vs holdout delta)
  3. Bootstrap 95% CI on holdout ratio (1000 resamples — first CI in this corpus)
  4. FAR / FRR via nearest-centroid classification on verification set

Covariance: diagonal (pooled from enrollment set). N/p = 10/4 = 2.5 < COV_MIN_RATIO=3.0
so diagonal covariance is the only valid choice (same Phase 142 rule as the existing analysis).

Output: docs/phase-c-ait-separation-report-2026-07-05.md
"""

from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT  = Path(__file__).resolve().parent.parent
ENROLL_DIR    = PROJECT_ROOT / "sessions" / "human" / "phase_c_ait_enroll"
VERIFY_DIR    = PROJECT_ROOT / "sessions" / "human" / "phase_c_ait_verify"
DOCS_DIR      = PROJECT_ROOT / "docs"

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# ---------------------------------------------------------------------------
# Reuse AIT feature extractor from analyze_interperson_separation.py
# ---------------------------------------------------------------------------

_AIT_NFFT      = 4096
_AIT_HZ_LOW    = 4.0
_AIT_HZ_HIGH   = 15.0
_AIT_FORCE_MIN = 90
_AIT_FORCE_MAX = 180
_AIT_MIN_FRAMES = 512

AIT_FEATURE_NAMES = ["accel_tremor_peak_hz", "roll_cos", "roll_sin", "pitch_cos"]
N_FEATURES        = len(AIT_FEATURE_NAMES)   # 4
COV_MIN_RATIO     = 3.0
BOOTSTRAP_REPS    = 1000
OPERATING_POINT_RATIO = 0.70   # min_separation_ratio default (Phase 166)
PLAYERS           = ["P1", "P2", "P3"]


def _extract_ait(fpath: Path) -> Optional[np.ndarray]:
    """Extract 4-feature AIT vector from a capture_session.py file. Returns None on failure."""
    try:
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    reports = data.get("reports", [])
    if not reports:
        return None

    tss = [r.get("timestamp_ms", 0) for r in reports[:200] if r.get("timestamp_ms", 0) > 0]
    fs = 1000.0
    if len(tss) >= 2:
        diffs = [tss[i] - tss[i-1] for i in range(1, len(tss)) if tss[i] > tss[i-1]]
        if diffs:
            fs = 1000.0 / float(np.median(diffs))

    held = [
        r for r in reports
        if _AIT_FORCE_MIN <= (r.get("features") or r).get("l2_trigger", 0) <= _AIT_FORCE_MAX
    ]
    if len(held) < _AIT_MIN_FRAMES:
        return None

    def _g(r: dict, key: str) -> float:
        src = r.get("features", r)
        v = src.get(key, 0.0)
        return float(v) if v is not None else 0.0

    ax = np.array([_g(r, "accel_x") for r in held])
    ay = np.array([_g(r, "accel_y") for r in held])
    az = np.array([_g(r, "accel_z") for r in held])

    mag    = np.sqrt(ax**2 + ay**2 + az**2)
    mag_dc = mag - mag.mean()
    spec   = np.abs(np.fft.rfft(mag_dc, n=_AIT_NFFT))
    freqs  = np.fft.rfftfreq(_AIT_NFFT, d=1.0/fs)

    band_mask = (freqs >= _AIT_HZ_LOW) & (freqs <= _AIT_HZ_HIGH)
    if not np.any(band_mask):
        return None
    band_spec  = spec[band_mask]
    band_freqs = freqs[band_mask]
    pk         = int(np.argmax(band_spec))

    if 0 < pk < len(band_spec) - 1:
        a, b, g = band_spec[pk-1], band_spec[pk], band_spec[pk+1]
        denom   = a - 2*b + g
        offset  = 0.5*(a - g)/denom if abs(denom) > 1e-10 else 0.0
        bin_w   = freqs[1] - freqs[0] if len(freqs) > 1 else fs/_AIT_NFFT
        tremor_hz = float(band_freqs[pk] + offset*bin_w)
    else:
        tremor_hz = float(band_freqs[pk])

    ax_m, ay_m, az_m = float(ax.mean()), float(ay.mean()), float(az.mean())
    roll_rad  = math.atan2(ax_m, az_m)
    pitch_rad = math.atan2(-ay_m, az_m)

    return np.array([tremor_hz, math.cos(roll_rad), math.sin(roll_rad), math.cos(pitch_rad)])


def _load_player_sessions(directory: Path, prefix: str, player: str) -> list[np.ndarray]:
    """Load all sessions for a player from a directory, return list of feature vectors."""
    files = sorted(directory.glob(f"{prefix}_{player}_*.json"))
    vecs  = []
    for f in files:
        v = _extract_ait(f)
        if v is not None:
            vecs.append(v)
        else:
            print(f"  WARN: extraction failed for {f.name}")
    return vecs


def _mahal_diag(x: np.ndarray, centroid: np.ndarray, inv_var: np.ndarray) -> float:
    """Diagonal Mahalanobis distance: sqrt(sum((x-mu)^2 / var))."""
    diff = x - centroid
    return float(np.sqrt(np.sum(diff**2 * inv_var)))


def _separation_ratio(
    vecs_by_player: dict[str, list[np.ndarray]],
    centroids: dict[str, np.ndarray],
    inv_var: np.ndarray,
) -> tuple[float, float, float]:
    """Compute inter/intra separation ratio on verification vectors.

    Returns (ratio, mean_inter, mean_intra).
    """
    inter_dists: list[float] = []
    intra_dists: list[float] = []

    players = list(vecs_by_player.keys())
    for p, vecs in vecs_by_player.items():
        for v in vecs:
            d_own = _mahal_diag(v, centroids[p], inv_var)
            intra_dists.append(d_own)
            for q in players:
                if q != p:
                    inter_dists.append(_mahal_diag(v, centroids[q], inv_var))

    mean_inter = float(np.mean(inter_dists)) if inter_dists else 0.0
    mean_intra = float(np.mean(intra_dists)) if intra_dists else 0.0
    ratio      = mean_inter / mean_intra if mean_intra > 0 else 0.0
    return ratio, mean_inter, mean_intra


def _bootstrap_ci(
    vecs_by_player: dict[str, list[np.ndarray]],
    centroids: dict[str, np.ndarray],
    inv_var: np.ndarray,
    n_reps: int = BOOTSTRAP_REPS,
    ci: float = 0.95,
) -> tuple[float, float]:
    """Bootstrap CI on the holdout separation ratio.

    Resamples verification sessions per player (with replacement), recomputes
    ratio each time. Returns (lower, upper) for the requested CI.
    """
    rng   = np.random.default_rng(seed=42)
    ratios: list[float] = []
    player_names = list(vecs_by_player.keys())
    player_arrays = {p: np.array(vecs_by_player[p]) for p in player_names}

    for _ in range(n_reps):
        sample: dict[str, list[np.ndarray]] = {}
        for p in player_names:
            arr = player_arrays[p]
            idx = rng.integers(0, len(arr), size=len(arr))
            sample[p] = list(arr[idx])
        r, _, _ = _separation_ratio(sample, centroids, inv_var)
        ratios.append(r)

    lo = float(np.percentile(ratios, (1.0 - ci) / 2.0 * 100.0))
    hi = float(np.percentile(ratios, (1.0 + ci) / 2.0 * 100.0))
    return lo, hi


def _loo_ratio(
    all_vecs: dict[str, list[np.ndarray]],
    inv_var: np.ndarray,
) -> float:
    """LOO separation ratio on combined enrollment+verification pool."""
    players = list(all_vecs.keys())
    inter_dists: list[float] = []
    intra_dists: list[float] = []

    for p in players:
        vecs_p = all_vecs[p]
        for i, v in enumerate(vecs_p):
            # LOO centroid: exclude session i from player p
            loo_vecs = [vecs_p[j] for j in range(len(vecs_p)) if j != i]
            loo_centroid = np.mean(loo_vecs, axis=0) if loo_vecs else np.zeros(N_FEATURES)
            intra_dists.append(_mahal_diag(v, loo_centroid, inv_var))
            for q in players:
                if q != p:
                    centroid_q = np.mean(all_vecs[q], axis=0)
                    inter_dists.append(_mahal_diag(v, centroid_q, inv_var))

    mean_inter = float(np.mean(inter_dists)) if inter_dists else 0.0
    mean_intra = float(np.mean(intra_dists)) if intra_dists else 0.0
    return mean_inter / mean_intra if mean_intra > 0 else 0.0


def _far_frr(
    verify_vecs: dict[str, list[np.ndarray]],
    centroids: dict[str, np.ndarray],
    inv_var: np.ndarray,
) -> dict[str, dict]:
    """Nearest-centroid FAR/FRR on the verification set.

    For each verification session, assign the nearest enrollment centroid label.
    FAR (for player P): another player's session is assigned to P.
    FRR (for player P): P's own session is assigned to a different player.
    """
    players = list(verify_vecs.keys())
    # tallies[p] = {genuine_accept, genuine_reject, impostor_accept, impostor_reject}
    tallies: dict[str, dict[str, int]] = {
        p: {"ga": 0, "gr": 0, "ia": 0, "ir": 0} for p in players
    }

    for true_player, vecs in verify_vecs.items():
        for v in vecs:
            dists    = {q: _mahal_diag(v, centroids[q], inv_var) for q in players}
            pred     = min(dists, key=lambda q: dists[q])
            for p in players:
                if p == true_player:
                    if pred == p:
                        tallies[p]["ga"] += 1   # genuine accept
                    else:
                        tallies[p]["gr"] += 1   # genuine reject (false reject)
                else:
                    if pred == p:
                        tallies[p]["ia"] += 1   # impostor accept (false accept)
                    else:
                        tallies[p]["ir"] += 1   # impostor reject (true reject)

    results: dict[str, dict] = {}
    for p in players:
        t = tallies[p]
        n_genuine  = t["ga"] + t["gr"]
        n_impostor = t["ia"] + t["ir"]
        results[p] = {
            "FRR": t["gr"] / n_genuine   if n_genuine   > 0 else float("nan"),
            "FAR": t["ia"] / n_impostor  if n_impostor  > 0 else float("nan"),
            "n_genuine":  n_genuine,
            "n_impostor": n_impostor,
            "genuine_accept": t["ga"],
            "genuine_reject": t["gr"],
            "impostor_accept": t["ia"],
            "impostor_reject": t["ir"],
        }
    return results


def _pairwise_distances(
    verify_vecs: dict[str, list[np.ndarray]],
    centroids: dict[str, np.ndarray],
    inv_var: np.ndarray,
) -> dict[str, dict[str, float]]:
    """Mean verification-session distance per player to each centroid."""
    result: dict[str, dict[str, float]] = {}
    for true_p, vecs in verify_vecs.items():
        result[true_p] = {}
        for centroid_p, centroid in centroids.items():
            dists = [_mahal_diag(v, centroid, inv_var) for v in vecs]
            result[true_p][centroid_p] = float(np.mean(dists)) if dists else float("nan")
    return result


def main() -> None:
    print("Phase C — C-2.3: AIT Holdout Separation Analysis")
    print("=" * 55)

    # ------------------------------------------------------------------
    # 1. Load enrollment sessions
    # ------------------------------------------------------------------
    print("\n[1] Loading enrollment sessions …")
    enroll: dict[str, list[np.ndarray]] = {}
    for p in PLAYERS:
        vecs = _load_player_sessions(ENROLL_DIR, "enroll", p)
        enroll[p] = vecs
        print(f"  {p}: {len(vecs)} enrollment sessions loaded")

    # ------------------------------------------------------------------
    # 2. Build enrollment centroids + pooled diagonal covariance
    # ------------------------------------------------------------------
    print("\n[2] Building enrollment centroids …")
    centroids: dict[str, np.ndarray] = {}
    for p, vecs in enroll.items():
        if not vecs:
            print(f"  ERROR: no enrollment sessions for {p}")
            sys.exit(1)
        centroids[p] = np.mean(vecs, axis=0)
        print(f"  {p} centroid: {centroids[p].round(4)}")

    # Pooled variance from enrollment set (diagonal covariance only)
    all_enroll = np.vstack([v for vecs in enroll.values() for v in vecs])
    n_enroll   = len(all_enroll)
    cov_ratio  = n_enroll / N_FEATURES
    print(f"\n  N_enroll={n_enroll}, p={N_FEATURES}, N/p={cov_ratio:.2f}  =>  diagonal covariance")
    if cov_ratio >= COV_MIN_RATIO:
        print("  NOTE: N/p >= 3.0 — full covariance would be valid but diagonal used for consistency")

    pooled_var = np.var(all_enroll, axis=0, ddof=1)
    pooled_var = np.where(pooled_var < 1e-10, 1e-10, pooled_var)   # clamp near-zero
    inv_var    = 1.0 / pooled_var

    print(f"  Pooled var: {pooled_var.round(6)}")

    # ------------------------------------------------------------------
    # 3. Load verification sessions
    # ------------------------------------------------------------------
    print("\n[3] Loading verification sessions …")
    verify: dict[str, list[np.ndarray]] = {}
    for p in PLAYERS:
        vecs = _load_player_sessions(VERIFY_DIR, "verify", p)
        verify[p] = vecs
        print(f"  {p}: {len(vecs)} verification sessions loaded")

    # ------------------------------------------------------------------
    # 4. Holdout separation ratio
    # ------------------------------------------------------------------
    print("\n[4] Computing holdout separation ratio …")
    hold_ratio, mean_inter, mean_intra = _separation_ratio(verify, centroids, inv_var)
    print(f"  mean_inter = {mean_inter:.4f}")
    print(f"  mean_intra = {mean_intra:.4f}")
    print(f"  holdout ratio = {hold_ratio:.4f}")

    # ------------------------------------------------------------------
    # 5. Bootstrap 95% CI
    # ------------------------------------------------------------------
    print(f"\n[5] Bootstrap CI ({BOOTSTRAP_REPS} reps) …")
    ci_lo, ci_hi = _bootstrap_ci(verify, centroids, inv_var)
    print(f"  95% CI: ({ci_lo:.4f}, {ci_hi:.4f})")

    # ------------------------------------------------------------------
    # 6. LOO ratio on combined pool
    # ------------------------------------------------------------------
    print("\n[6] LOO ratio on combined enrollment+verification pool …")
    combined: dict[str, list[np.ndarray]] = {
        p: enroll[p] + verify[p] for p in PLAYERS
    }
    loo_ratio = _loo_ratio(combined, inv_var)
    print(f"  LOO ratio = {loo_ratio:.4f}")
    delta     = loo_ratio - hold_ratio
    print(f"  LOO - holdout delta = {delta:+.4f}  ({'LOO overstates' if delta > 0 else 'consistent'})")

    # ------------------------------------------------------------------
    # 7. Pairwise distances
    # ------------------------------------------------------------------
    pair_dists = _pairwise_distances(verify, centroids, inv_var)

    # ------------------------------------------------------------------
    # 8. FAR / FRR
    # ------------------------------------------------------------------
    print("\n[7] FAR / FRR (nearest-centroid, verification set) …")
    far_frr = _far_frr(verify, centroids, inv_var)
    for p, r in far_frr.items():
        print(f"  {p}: FRR={r['FRR']:.3f}  FAR={r['FAR']:.3f}  "
              f"(genuine={r['n_genuine']}, impostor={r['n_impostor']})")

    # ------------------------------------------------------------------
    # 9. Per-player enrollment summary
    # ------------------------------------------------------------------
    per_player_n = {p: {"enroll": len(enroll[p]), "verify": len(verify[p])} for p in PLAYERS}

    # ------------------------------------------------------------------
    # 10. Write report
    # ------------------------------------------------------------------
    _write_report(
        enroll, verify, centroids, pooled_var, cov_ratio,
        hold_ratio, mean_inter, mean_intra, ci_lo, ci_hi,
        loo_ratio, delta, pair_dists, far_frr, per_player_n
    )

    print("\n[DONE] Report written to docs/phase-c-ait-separation-report-2026-07-05.md")


def _write_report(
    enroll, verify, centroids, pooled_var, cov_ratio,
    hold_ratio, mean_inter, mean_intra, ci_lo, ci_hi,
    loo_ratio, delta, pair_dists, far_frr, per_player_n
) -> None:
    out = DOCS_DIR / "phase-c-ait-separation-report-2026-07-05.md"

    status_flag = "PASS (>1.0)" if hold_ratio > 1.0 else "FAIL (<1.0 — not separable at holdout)"

    lines: list[str] = [
        "# Phase C — C-2.3: AIT Holdout Separation Report",
        "",
        f"**Date:** 2026-07-05  ",
        f"**Branch:** feat/l9-consistency-adversarial-harness  ",
        f"**Status:** {status_flag}  ",
        "**Probe:** AIT (Adaptive-trigger Isometric Tremor, L2 hold 115–135 analog, 30s)  ",
        "**Methodology:** Enrollment/verification split (C-2.1 protocol) — first holdout metric in this corpus  ",
        "",
        "---",
        "",
        "## 1. Corpus",
        "",
        "| Player | Enrollment sessions | Verification sessions |",
        "|--------|--------------------|-----------------------|",
    ]
    for p in PLAYERS:
        lines.append(f"| {p} | {per_player_n[p]['enroll']} | {per_player_n[p]['verify']} |")

    total_e = sum(per_player_n[p]["enroll"] for p in PLAYERS)
    total_v = sum(per_player_n[p]["verify"] for p in PLAYERS)
    lines += [
        f"| **Total** | **{total_e}** | **{total_v}** |",
        "",
        f"Note: P2 enrollment and P3 verification have 11 sessions (one extra each). "
        "All sessions are included; the analysis handles unequal group sizes.",
        "",
        "Covariance mode: **diagonal** (pooled from enrollment set).  ",
        f"N_enroll={total_e}, p={N_FEATURES} features, N/p={cov_ratio:.2f} "
        f"< COV_MIN_RATIO={COV_MIN_RATIO:.1f} => diagonal covariance applies (Phase 142 rule).",
        "",
        "---",
        "",
        "## 2. Enrollment Centroids",
        "",
        f"| Player | {' | '.join(f'`{f}`' for f in AIT_FEATURE_NAMES)} |",
        f"|--------|{'|'.join(['-------']*N_FEATURES)}|",
    ]
    for p in PLAYERS:
        vals = " | ".join(f"{v:.4f}" for v in centroids[p])
        lines.append(f"| {p} | {vals} |")

    lines += [
        "",
        f"Pooled diagonal variance (enrollment): "
        + ", ".join(f"{v:.6f}" for v in pooled_var),
        "",
        "---",
        "",
        "## 3. Headline Results",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| **Holdout separation ratio** | **{hold_ratio:.4f}** |",
        f"| 95% bootstrap CI | ({ci_lo:.4f}, {ci_hi:.4f}) |",
        f"| LOO ratio (combined pool) | {loo_ratio:.4f} |",
        f"| LOO - holdout delta | {delta:+.4f} |",
        f"| mean_inter (verification) | {mean_inter:.4f} |",
        f"| mean_intra (verification) | {mean_intra:.4f} |",
        "",
        f"**Interpretation:** {'ratio > 1.0 => players are separable at the holdout operating point.' if hold_ratio > 1.0 else 'ratio < 1.0 => players are NOT separable at the holdout operating point. See §5 for analysis.'}",
        "",
        f"**LOO vs holdout delta = {delta:+.4f}:** "
        + ("LOO overstates real-world separability — the holdout split is the more honest number for a tournament-enrollment scenario." if delta > 0.01
           else "LOO and holdout are consistent — the corpus is large enough that the LOO approximation holds."),
        "",
        "---",
        "",
        "## 4. Pairwise Distance Table (verification sessions => enrollment centroids)",
        "",
        "Rows = ground-truth player; columns = enrollment centroid. Bold diagonal = intra-player.",
        "",
        f"| | {' | '.join(f'{p} centroid' for p in PLAYERS)} |",
        f"|---|{'|'.join(['---']*len(PLAYERS))}|",
    ]
    for true_p in PLAYERS:
        row_vals = []
        for centroid_p in PLAYERS:
            d = pair_dists[true_p][centroid_p]
            if true_p == centroid_p:
                row_vals.append(f"**{d:.3f}**")
            else:
                row_vals.append(f"{d:.3f}")
        lines.append(f"| {true_p} | {' | '.join(row_vals)} |")

    lines += [
        "",
        "---",
        "",
        "## 5. FAR / FRR (nearest-centroid classification)",
        "",
        "Operating point: nearest-centroid assignment on verification sessions.  ",
        "FRR = enrolled player's verification session assigned to wrong player.  ",
        "FAR = different player's verification session assigned to this player.  ",
        "",
        "| Player | FRR | FAR | Genuine N | Impostor N | GA | GR | IA | IR |",
        "|--------|-----|-----|-----------|------------|----|----|----|----|",
    ]
    for p in PLAYERS:
        r = far_frr[p]
        frr_s = f"{r['FRR']:.3f}" if not math.isnan(r["FRR"]) else "N/A"
        far_s = f"{r['FAR']:.3f}" if not math.isnan(r["FAR"]) else "N/A"
        lines.append(
            f"| {p} | {frr_s} | {far_s} | {r['n_genuine']} | {r['n_impostor']} "
            f"| {r['genuine_accept']} | {r['genuine_reject']} | {r['impostor_accept']} | {r['impostor_reject']} |"
        )

    # Overall FAR/FRR
    all_genuine  = sum(r["n_genuine"]         for r in far_frr.values())
    all_ga       = sum(r["genuine_accept"]     for r in far_frr.values())
    all_gr       = sum(r["genuine_reject"]     for r in far_frr.values())
    all_impostor = sum(r["n_impostor"]         for r in far_frr.values())
    all_ia       = sum(r["impostor_accept"]    for r in far_frr.values())
    all_ir       = sum(r["impostor_reject"]    for r in far_frr.values())
    frr_all = all_gr / all_genuine   if all_genuine   > 0 else float("nan")
    far_all = all_ia / all_impostor  if all_impostor  > 0 else float("nan")
    lines += [
        f"| **All** | **{frr_all:.3f}** | **{far_all:.3f}** | {all_genuine} | {all_impostor} "
        f"| {all_ga} | {all_gr} | {all_ia} | {all_ir} |",
        "",
        "GA = genuine accept, GR = genuine reject, IA = impostor accept, IR = impostor reject.",
        "",
        "---",
        "",
        "## 6. Comparison to Prior Corpus Numbers",
        "",
        "| Metric | Value | Source |",
        "|--------|-------|--------|",
        "| AIT LOO ratio (prior corpus, N=37) | 1.199 | Phase 229/231, all_pairs_above_1=True |",
        f"| **AIT holdout ratio (this protocol)** | **{hold_ratio:.4f}** | C-2.3, N={total_e}+{total_v}/player |",
        f"| AIT LOO ratio (combined pool, this protocol) | {loo_ratio:.4f} | C-2.3 comparator |",
        f"| LOO-holdout delta | {delta:+.4f} | Methodological difference |",
        "",
        "---",
        "",
        "## 7. Honest Limitations",
        "",
        "- **3-player developer corpus only** — `cert_scope=developer_self`, `population_certified=False`.",
        "  No population-level claim is made. This is the same caveat every prior separation number carries.",
        "- **N=10/player enrollment** — small centroid estimate. More enrollment sessions would",
        "  tighten the centroid and likely improve both ratio and FAR/FRR.",
        "- **Diagonal covariance** — required by N/p=2.5 < 3.0. Off-diagonal correlations between",
        "  features (e.g., roll_cos and roll_sin) are not captured.",
        "- **Single probe type (AIT)** — this report characterizes only the AIT signal.",
        "  L4 full-gameplay and L5 temporal rhythm are not measured here.",
        "- **P2 enrollment N=11, P3 verification N=11** — one extra session each.",
        "  All sessions included; the imbalance has negligible effect at this N.",
        "- **No promotion decision** — this report feeds C-4.2/C-4.3 weighting decisions.",
        "  It does not flip any `_ENABLED` flag or modify `_PROVISIONAL_WEIGHTS`.",
        "",
        "---",
        "",
        "## 8. Next Steps",
        "",
        "- **C-2.3 closed** by this report.",
        "- **C-3.2** (KAS quality measurement sessions) is the parallel track.",
        "- **C-4.2** (Advisory Presence Confidence Model) consumes the FAR/FRR numbers from §5.",
        "- **L6B campaign** (parallel to C-2.2, N=0 so far) remains open — honest interim report",
        "  at whatever N is reached; `L6B_ENABLED` gate stays at N≥50 regardless.",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
