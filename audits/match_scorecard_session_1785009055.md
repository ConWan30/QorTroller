================================================================
  QorTroller Match Self-Scorecard  (VALID-1)
================================================================
  Schema   : qortroller-match-scorecard-v1
  Label    : session_1785009055
  Pack     : observer-only
  Session  : fabe241501b04c50087eb4a13266b7254499e4bcfa8a043435c97017da2d8fc5  [OK]
  Node     : 01a574e7ca7f  [DERIVED]  domain=QORTROLLER-NODE-v0
             (full node_id DERIVED -- not on-chain; device 581a836c98b3... + birth)
----------------------------------------------------------------
  RECALL (load-bearing rail)
  status   : UNSCORED
  display  : authored 0 / reported UNSCORED
  authored : 0  [MEASURED]
  reported : None  [OPERATOR-REPORTED]
  ratio    : None  [ABSENT]
  note     : denominator is OPERATOR-REPORTED only — never killfeed / c33 / invented 0
----------------------------------------------------------------
  AUTHORSHIP LAYERS (WA-01: WITNESSED ⊂ BOUND ⊂ AUTHORED — never collapsed)
  witnessed: None  [ABSENT]  (node saw your name in the killer slot)
  bound    : None  [ABSENT]  (R2-window — not persisted to KAS record yet)
  authored : 0  [MEASURED]  (strict causal + hygiene)
  observation_verdict : None  [DERIVED]  (product tier; NOT a KAS commitment)
  topology : DUAL_CONNECTION_USB_PC  ->  authorship_reachable=WITNESSED_ONLY
             R2 onsets not visible on capture-PC HID (ts_source=wall_fallback); AUTHORED needs USB-only-to-PS5 or a PoEP presence path
  note     : witnessed 17 · bound 3 · authored 0 is an HONEST STOP POINT, not '0 kills' —
             the chain shows exactly where dual-connection blocks causal promotion.
----------------------------------------------------------------
  KAS      : HYGIENE_FAIL  [MEASURED]
  PoSP     : SYNCHRONIZED  [MEASURED]
  fusion_n : 142  [MEASURED]
  v3 events: None  [ABSENT]
  sink rows: None  [ABSENT]  (NOT scored kills)
----------------------------------------------------------------
  False-authorship language (MAY only):
   + A2/A3 structural guards CLOSED (exact-token killer match + leftmost-killer death path)
   + authored kills are R2-bound on the KAS path (design invariant of the authorship chain)
   + zero-false-read *design*: this scorecard never invents authored kills from OCR alone
  MUST NOT claim:
   - zero false-authorship proven this match
   - 0 false positives proven
   - 100% accurate authorship
   - false-authorship rate = 0
   - precision = 100%
----------------------------------------------------------------
  Dignity tone: honest_null
   * authored=0 is a legitimate observation (no R2-bound authored kills this session), not a player failure
   * recall UNSCORED: denominator is operator-only; declining or omitting D is valid
  Dogfood     : ABSENT (honest-null — not a fail)
  Birth       : path=A  first_session_id=proof_drill_20260713_1843_1783986208
               node_id=01a574e7ca7f... (DERIVED, not minted)
----------------------------------------------------------------
  Provenance: MEASURED = our instruments; OPERATOR-REPORTED = only they know;
  DERIVED = arithmetic over tagged inputs; ABSENT = honest-null.
  node_id = DERIVED spine (device_id + birth); DEVICE may be on-chain, node_id is not.
  A match self-score that over-claims is worse than no score.
================================================================
