// Manifest schema validator — pure-TS, no runtime deps.
//
// Decision D1 (1-A): solo workspace, no monorepo edges. Validation is local-only.
// Decision D2 (2-C): mount-agnostic — manifest does not assume any specific mount route.
// INV-BRP-1 (draft): live-flag honesty is the load-bearing property; this validator is
// what enforces, at the schema level, that every entry has a live: boolean field.

export interface ManifestEntry {
  readonly live: boolean;
  readonly reason: string;
  readonly implemented?: boolean;
  readonly path?: string;
}

export interface PvCiDraftEntry extends ManifestEntry {
  readonly summary: string;
  readonly drafted_at: string;
  readonly added_to_pv_ci_gate: boolean;
}

export interface HashLibraryRecord {
  readonly name: string;
  readonly version_constraint: string;
  readonly exports_used: readonly string[];
  readonly substituted_from: string;
  readonly substitution_reason: string;
}

export interface HashDomainRecord {
  readonly string: string;
  readonly purpose: string;
  readonly reserved_at_ceremony: boolean;
  readonly collision_check_against_existing_v1_tags: readonly string[];
  readonly collision_status: string;
}

export interface LiveFlagTransitionRules {
  readonly summary: string;
  readonly preconditions: readonly string[];
  readonly no_unilateral_flip: boolean;
  readonly default_state_until_ceremony: boolean;
}

export interface BrpManifest {
  readonly version: string;
  readonly track_classification: "out-of-band-solo";
  readonly phase_number: null;
  readonly track_disclaimer: string;
  readonly hash_library: HashLibraryRecord;
  readonly hash_domain: HashDomainRecord;
  readonly components: Readonly<Record<string, ManifestEntry>>;
  readonly modules: Readonly<Record<string, ManifestEntry>>;
  readonly fixtures: Readonly<Record<string, ManifestEntry>>;
  readonly adapters: Readonly<Record<string, ManifestEntry>>;
  readonly docs: Readonly<Record<string, ManifestEntry>>;
  readonly pv_ci_drafts: Readonly<Record<string, PvCiDraftEntry>>;
  readonly live_flag_transition_rules: LiveFlagTransitionRules;
}

export interface ValidationResult {
  readonly ok: boolean;
  readonly violations: readonly string[];
}

const REQUIRED_TOP_LEVEL_KEYS = [
  "version",
  "track_classification",
  "phase_number",
  "track_disclaimer",
  "hash_library",
  "hash_domain",
  "components",
  "modules",
  "fixtures",
  "adapters",
  "docs",
  "pv_ci_drafts",
  "live_flag_transition_rules",
] as const;

const ENTRY_BUCKETS = ["components", "modules", "fixtures", "adapters", "docs"] as const;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateEntry(
  bucket: string,
  key: string,
  raw: unknown,
  violations: string[],
): void {
  if (!isPlainObject(raw)) {
    violations.push(`${bucket}.${key}: entry must be an object`);
    return;
  }
  if (typeof raw["live"] !== "boolean") {
    violations.push(
      `${bucket}.${key}: missing or non-boolean 'live' field (INV-BRP-1 draft requires every entry carry an explicit boolean)`,
    );
  }
  if (typeof raw["reason"] !== "string" || (raw["reason"] as string).length === 0) {
    violations.push(`${bucket}.${key}: missing or empty 'reason' string`);
  }
}

export function validateManifest(input: unknown): ValidationResult {
  const violations: string[] = [];

  if (!isPlainObject(input)) {
    return { ok: false, violations: ["manifest must be a JSON object"] };
  }

  for (const key of REQUIRED_TOP_LEVEL_KEYS) {
    if (!(key in input)) {
      violations.push(`top-level: missing required key '${key}'`);
    }
  }

  if (input["track_classification"] !== "out-of-band-solo") {
    violations.push(
      `track_classification must be exactly "out-of-band-solo" (honesty-first invariant); got: ${JSON.stringify(input["track_classification"])}`,
    );
  }

  if (input["phase_number"] !== null) {
    violations.push(
      `phase_number must be exactly null (this track is not numbered as a phase); got: ${JSON.stringify(input["phase_number"])}`,
    );
  }

  for (const bucket of ENTRY_BUCKETS) {
    const value = input[bucket];
    if (!isPlainObject(value)) {
      violations.push(`${bucket}: must be an object map (got ${typeof value})`);
      continue;
    }
    for (const [key, raw] of Object.entries(value)) {
      validateEntry(bucket, key, raw, violations);
    }
  }

  const drafts = input["pv_ci_drafts"];
  if (isPlainObject(drafts)) {
    for (const [key, raw] of Object.entries(drafts)) {
      if (!isPlainObject(raw)) {
        violations.push(`pv_ci_drafts.${key}: entry must be an object`);
        continue;
      }
      validateEntry("pv_ci_drafts", key, raw, violations);
      if (typeof raw["summary"] !== "string") {
        violations.push(`pv_ci_drafts.${key}: missing 'summary' string`);
      }
      if (typeof raw["drafted_at"] !== "string") {
        violations.push(`pv_ci_drafts.${key}: missing 'drafted_at' string`);
      }
      if (raw["added_to_pv_ci_gate"] !== false) {
        violations.push(
          `pv_ci_drafts.${key}: added_to_pv_ci_gate must be false (this commit does not modify PV-CI gate)`,
        );
      }
    }
  }

  const hashDomain = input["hash_domain"];
  if (isPlainObject(hashDomain)) {
    if (hashDomain["string"] !== "VAPI-BRP-RENDER-v1") {
      violations.push(
        `hash_domain.string must be exactly "VAPI-BRP-RENDER-v1"; got ${JSON.stringify(hashDomain["string"])}`,
      );
    }
  }

  return { ok: violations.length === 0, violations };
}
