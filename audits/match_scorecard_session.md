================================================================
  QorTroller Match Self-Scorecard  (VALID-1)
================================================================
  Schema   : qortroller-match-scorecard-v1
  Label    : session
  Pack     : observer-only
  Session  : d07b169f4985da9aafb73b3e79b97fd60233940b36cea8d7e48c74155c5ca298  [OK]
  Node     : (null)  [ABSENT]  (honest -- node_id needs birth + public device_id)
----------------------------------------------------------------
  RECALL (load-bearing rail)
  status   : SCORED
  display  : authored 0 [MEASURED] / reported 2 [OPERATOR-REPORTED]  (= 0.0000 DERIVED, unrounded)
  authored : 0  [MEASURED]
  reported : 2  [OPERATOR-REPORTED]
  ratio    : 0.0  [DERIVED]
  note     : denominator is OPERATOR-REPORTED only — never killfeed / c33 / invented 0
----------------------------------------------------------------
  KAS      : HYGIENE_FAIL  [MEASURED]
  PoSP     : SYNCHRONIZED  [MEASURED]
  fusion_n : 72  [MEASURED]
  v3 events: 5  [MEASURED]
  sink rows: 5  [MEASURED]  (NOT scored kills)
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
  Dogfood     : ABSENT (honest-null — not a fail)
  Birth       : ABSENT (honest-null)
----------------------------------------------------------------
  Provenance: MEASURED = our instruments; OPERATOR-REPORTED = only they know;
  DERIVED = arithmetic over tagged inputs; ABSENT = honest-null.
  node_id = DERIVED spine (device_id + birth); DEVICE may be on-chain, node_id is not.
  A match self-score that over-claims is worse than no score.
================================================================
