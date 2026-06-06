// Sample fixture bundle for /research try-it-now panel.
// Matches the shape produced by bridge/vapi_bridge/wmp/bundle_assembler.py
// exactly so the in-browser verifier produces identical results to the
// Python verifier (sdk/wmp_verify.py).
//
// scope_synthetic: true is honest — this IS a synthetic fixture. The
// /research verifier panel runs with allowSynthetic: true so the fixture
// VERIFIES; if a researcher pastes a real corpus bundle, they should
// toggle that off and any synthetic bundle will REJECT honestly.

export const SAMPLE_BUNDLE = {
  schema: 'vapi-wmp-provenance-bundle-v1',
  bundle_created_at_ns: 1780718400000000000,

  // action_trace — 8 ticks of zero-bytes per channel (the simplest valid
  // post-φ matrix; produces a deterministic structural rehash digest)
  action_trace_format: 'quantized_macro_intent_60hz',
  action_trace_channels: [
    'stick_L_sector',
    'stick_R_sector',
    'trigger_L_state',
    'trigger_R_state',
    'button_mask',
    'imu_gravity_sector',
  ],
  action_trace_ticks: 8,
  sanitized_trace_root_ref: '143000',
  action_trace_matrix_hex: {
    stick_L_sector:      '0000000000000000',
    stick_R_sector:      '0000000000000000',
    trigger_L_state:     '0000000000000000',
    trigger_R_state:     '0000000000000000',
    button_mask:         '00000000000000000000000000000000',
    imu_gravity_sector:  '0000000000000000',
  },

  // humanity_proof — 256-byte ML-DSA-65 / Groth16 proof bytes hex
  humanity_proof_type: 'VAPI-REPLAY-PROOF-v1',
  humanity_proof_bytes_hex: '0x' + 'ab'.repeat(256),
  humanity_proof_public_inputs: {
    sanitizedTraceRoot: '143000',
    poacChainRoot:      '0',
  },
  humanity_verifier_address: '0x5182372d1D033db0c9230843DFDE606733D5F91B',
  humanity_deferred: false,
  humanity_deferred_reason: '',

  // recency — empty registry → BEACON_REGISTRY_NOT_DEPLOYED honest deferral
  recency_open_block:       0,
  recency_open_block_hash:  '',
  recency_close_block:      0,
  recency_close_block_hash: '',
  recency_registry_address: '',

  // consent — W1-D DEFERRED in v1
  consent_registry_address: '0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743',
  consent_gamer_address:    '0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692',
  consent_manifest_hash:    '0x00d2be8fbd80b9475724f38c858ea6e7d1f690ff893de52d790424bc762ba358',
  world_model_consent_dimension: 'DEFERRED',
  world_model_consent_registry: '',

  // scope_disclosure — FROZEN values
  scope_channel: 'ACTION_ONLY',
  scope_observation_channel: 'ABSENT_BY_DESIGN_DATA_FLOOR',
  scope_fidelity: 'MACRO_INTENT_POST_PHI_NOT_BIOMECHANICAL',
  scope_synthetic: true,
  scope_is_full_pomdp_tuple: false,
}
