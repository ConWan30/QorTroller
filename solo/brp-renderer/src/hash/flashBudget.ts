// flashBudget — pure-function form of the WCAG 2.3.1 / G19 / G176 / ΔL static analyzer.
//
// Pre-R3F. Accepts a declarative MaterialDescriptor and decides ok/violations.
// The R3F integration in commit 2+ will feed this from scene-graph traversal.
//
// PDF reference: §"Block A1 — Accessibility & photosensitivity governance" and
// §"WCAG 2.3.1 (Three Flashes or Below Threshold)".
//
// Three sufficient pathways per WCAG 2.3.1; ANY ONE passing is sufficient:
//   G19:  oscillator frequency < 3 Hz.
//   G176: animated area on-screen < 87,296 CSS px² (W3C verbatim threshold).
//   ΔL:   |Δ relative luminance| between any pair of opposing extrema < 0.10
//         (per WCAG general flash threshold).
//
// Additional saturated-red guard: reject transitions where R/(R+G+B) >= 0.8 with
// a Δuv > 0.2 in the CIE 1976 UCS chromaticity diagram (per WCAG 2.2 working
// definition). The pure-function form here uses a simplified scalar input that
// callers (commit 2+) will derive from full chromaticity data.

export interface MaterialDescriptor {
  /** Identifier surfaced in violation messages. */
  readonly id: string;
  /** Frequency, Hz, of the dominant luminance oscillator on this material. */
  readonly frequency_hz: number;
  /** On-screen footprint of the animated region, in CSS pixels squared. */
  readonly area_css_px2: number;
  /** Maximum |Δ relative luminance| between any pair of opposing extrema. */
  readonly delta_luminance: number;
  /** Whether the transition is to/from a saturated-red state per WCAG 2.2 def. */
  readonly is_saturated_red: boolean;
  /** Δuv in the CIE 1976 UCS chromaticity diagram, paired with is_saturated_red. */
  readonly chromaticity_delta_uv?: number;
}

export interface FlashBudgetResult {
  readonly ok: boolean;
  readonly violations: readonly string[];
  /** Which pathway carried the pass, if any. */
  readonly pathway: "G19" | "G176" | "DELTA_L" | null;
}

// W3C-verbatim thresholds. Do not alter without a WCAG reference.
export const G19_FREQUENCY_HZ_CAP = 3;
export const G176_AREA_CSS_PX2_CAP = 87_296;
export const DELTA_L_CAP = 0.1;
export const SATURATED_RED_DELTA_UV_CAP = 0.2;

export function evaluateFlashBudget(m: MaterialDescriptor): FlashBudgetResult {
  const violations: string[] = [];

  // Saturated-red guard fires regardless of pathway: per WCAG 2.2, this is a
  // hard reject, not a pathway choice.
  if (m.is_saturated_red) {
    const duv = m.chromaticity_delta_uv ?? 0;
    if (duv > SATURATED_RED_DELTA_UV_CAP) {
      violations.push(
        `${m.id}: saturated-red transition with Δuv=${duv} exceeds ${SATURATED_RED_DELTA_UV_CAP} (WCAG 2.2 working definition)`,
      );
      return { ok: false, violations, pathway: null };
    }
  }

  // G19: oscillator frequency cap.
  if (m.frequency_hz < G19_FREQUENCY_HZ_CAP) {
    return { ok: true, violations: [], pathway: "G19" };
  }

  // G176: animated-area cap.
  if (m.area_css_px2 < G176_AREA_CSS_PX2_CAP) {
    return { ok: true, violations: [], pathway: "G176" };
  }

  // ΔL clamp.
  if (m.delta_luminance < DELTA_L_CAP) {
    return { ok: true, violations: [], pathway: "DELTA_L" };
  }

  violations.push(
    `${m.id}: no WCAG 2.3.1 pathway satisfied — ` +
      `frequency_hz=${m.frequency_hz} (cap ${G19_FREQUENCY_HZ_CAP}), ` +
      `area_css_px2=${m.area_css_px2} (cap ${G176_AREA_CSS_PX2_CAP}), ` +
      `delta_luminance=${m.delta_luminance} (cap ${DELTA_L_CAP})`,
  );
  return { ok: false, violations, pathway: null };
}

/**
 * Evaluate every material in a scene. The scene fails if any material fails.
 */
export function evaluateScene(
  materials: readonly MaterialDescriptor[],
): FlashBudgetResult {
  const violations: string[] = [];
  for (const mat of materials) {
    const r = evaluateFlashBudget(mat);
    if (!r.ok) {
      for (const v of r.violations) violations.push(v);
    }
  }
  return { ok: violations.length === 0, violations, pathway: null };
}
