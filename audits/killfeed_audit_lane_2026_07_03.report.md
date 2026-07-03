# Kill-feed audit lane — dual-instrument precision report
Crops: **611** from `C:\Users\Contr\vapi-pebble-prototype\retina_kf_crops`  ·  2047.2 ms/crop
Ensemble (Instrument B): feed_v1, roster_v1, session_anchor:session_anchor_20260703_075738_b0b9f31a24bb1e98.png, session_anchor:session_anchor_replay2_280a1f1513688989.png  ·  R4 session anchors: **2**

## Zero-false-read bar (the hard gate)
- Instrument A OWN_KILL reads: **35**
- **Candidate false reads** (A=OWN_KILL contradicted by B seeing the handle in a non-killer slot): **3** — bar is ZERO after adjudication; see contact sheet.

## Per-instrument taxonomy
- A `ocr_row_v1` (killer-slot READER): {'UNRESOLVED': 576, 'OWN_KILL': 35}
- B `template_ensemble_v1` (template SCORER): {'UNRESOLVED': 338, 'OWN_KILL': 57, 'OTHER_ROW': 185, 'OWN_DEATH': 31}
- UNRESOLVED rate — A **94.3%** / B **55.3%** (pre-registered DRIFT ALARM: a rendering change spikes this before recall silently collapses)

## Disagreement report (the independence measurement)
{'B_KILL_A_MISS': 25, 'CONFLICT_A_KILL_B_ROSTER': 2, 'CONFLICT_A_KILL_B_DEATH': 1}

Categories: `CONFLICT_A_KILL_B_DEATH`/`_B_ROSTER` = candidate A false read (contact sheet); `A_KILL_B_GAP` = EXPECTED B-coverage gap (B had no R4 anchor for the rendering — NOT suspicion); `A_KILL_B_MISS` = B had an R4 anchor but missed (real B miss); `B_KILL_A_MISS` = A OCR recall gap.

## Instrument B coverage annotation (uneven by construction)
B's OWN_KILLs by winning anchor: {'feed_v1': 2, 'session_anchor:session_anchor_20260703_075738_b0b9f31a24bb1e98.png': 25, 'session_anchor:session_anchor_replay2_280a1f1513688989.png': 28, 'roster_v1': 2}

> **B-coverage: includes R4.** At least one B OWN_KILL was carried by an R4 session anchor (session_anchor:session_anchor_20260703_075738_b0b9f31a24bb1e98.png, session_anchor:session_anchor_replay2_280a1f1513688989.png) — A-B agreement corroborates independence over that covered subset.

## Correlated blind spot (honest limit)
- Crops neither instrument resolved (UNRESOLVED by BOTH): **338** — the deep tail where feed_v1 < 0.40 (A cannot locate) AND template < 0.66 (B sub-floor). This is the human_oracle contact-sheet input.
