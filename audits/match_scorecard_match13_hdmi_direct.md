================================================================
  QorTroller Match Self-Scorecard  (VALID-1)
================================================================
  Schema   : qortroller-match-scorecard-v1
  Label    : match13_hdmi_direct
  Pack     : observer-only
  Session  : 0283fc1e400999426c6af613325579b577c73d3ede5ce79abaeeb2fd80509b86  [OK]
----------------------------------------------------------------
  RECALL (load-bearing rail)
  status   : SCORED
  display  : authored 8 [MEASURED] / reported 21 [OPERATOR-REPORTED]  (= 0.3810 DERIVED, unrounded)
  authored : 8  [MEASURED]
  reported : 21  [OPERATOR-REPORTED]
  ratio    : 0.38095238095238093  [DERIVED]
  note     : denominator is OPERATOR-REPORTED only — never killfeed / c33 / invented 0
----------------------------------------------------------------
  KAS      : AUTHORED_SESSION  [MEASURED]
  PoSP     : SYNCHRONIZED  [MEASURED]
  fusion_n : 358  [MEASURED]
  v3 events: None  [ABSENT]
  sink rows: 2  [MEASURED]  (NOT scored kills)
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
  Dignity tone: earned
  Dogfood     : ABSENT (honest-null — not a fail)
  Birth       : ABSENT (honest-null)
----------------------------------------------------------------
  Provenance: MEASURED = our instruments; OPERATOR-REPORTED = only they know;
  DERIVED = arithmetic over tagged inputs; ABSENT = honest-null.
  A match self-score that over-claims is worse than no score.
================================================================
