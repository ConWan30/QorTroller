# Kill-feed audit lane — dual-instrument precision report
Crops: **619** from `C:\Users\Contr\vapi-pebble-prototype\retina_kf_archive/sess_hid_v1_1783174566`  ·  2063.5 ms/crop
Ensemble (Instrument B): feed_v1, roster_v1, session_anchor:session_anchor_20260703_075738_b0b9f31a24bb1e98.png, session_anchor:session_anchor_20260703_130045_d9b52b6054b0f699.png, session_anchor:session_anchor_20260703_131828_c7dd3b58985cbd6c.png, session_anchor:session_anchor_20260703_133007_0fe744907416e4c6.png, session_anchor:session_anchor_20260703_141526_5ec2595697e0aa6b.png, session_anchor:session_anchor_20260703_141526_8e65da13b760735e.png, session_anchor:session_anchor_20260703_155058_b46bd348749c2ed5.png, session_anchor:session_anchor_20260703_162507_f2517c9d99b348b2.png, session_anchor:session_anchor_20260703_232037_bd0f6fc026ff3957.png, session_anchor:session_anchor_20260704_091615_0a434bb9b883112a.png, session_anchor:session_anchor_20260704_130602_f973615d792637b9.png, session_anchor:session_anchor_brval_66d7482992a0fff6.png, session_anchor:session_anchor_replay2_280a1f1513688989.png, session_anchor:session_anchor_replay_39767eb130325aa4.png, session_anchor:session_anchor_replay_51a7237c4f00ae45.png, session_anchor:session_anchor_replay_5475493d35b3f719.png, session_anchor:session_anchor_replay_b0b9f31a24bb1e98.png  ·  R4 session anchors: **17**

## Zero-false-read bar (the hard gate)
- Instrument A OWN_KILL reads: **101**
- **Candidate false reads** (A=OWN_KILL contradicted by B seeing the handle in a non-killer slot): **2** — bar is ZERO after adjudication; see contact sheet.

## Per-instrument taxonomy
- A `ocr_row_v1` (killer-slot READER): {'UNRESOLVED': 518, 'OWN_KILL': 101}
- B `template_ensemble_v1` (template SCORER): {'OTHER_ROW': 212, 'OWN_KILL': 192, 'UNRESOLVED': 107, 'OWN_DEATH': 108}
- UNRESOLVED rate — A **83.7%** / B **17.3%** (pre-registered DRIFT ALARM: a rendering change spikes this before recall silently collapses)

## Disagreement report (the independence measurement)
{'B_KILL_A_MISS': 93, 'CONFLICT_A_KILL_B_ROSTER': 1, 'CONFLICT_A_KILL_B_DEATH': 1}

Categories: `CONFLICT_A_KILL_B_DEATH`/`_B_ROSTER` = candidate A false read (contact sheet); `A_KILL_B_GAP` = EXPECTED B-coverage gap (B had no R4 anchor for the rendering — NOT suspicion); `A_KILL_B_MISS` = B had an R4 anchor but missed (real B miss); `B_KILL_A_MISS` = A OCR recall gap.

## Instrument B coverage annotation (uneven by construction)
B's OWN_KILLs by winning anchor: {'session_anchor:session_anchor_20260703_141526_5ec2595697e0aa6b.png': 70, 'session_anchor:session_anchor_20260703_075738_b0b9f31a24bb1e98.png': 13, 'session_anchor:session_anchor_replay_39767eb130325aa4.png': 34, 'session_anchor:session_anchor_20260703_232037_bd0f6fc026ff3957.png': 12, 'session_anchor:session_anchor_20260704_091615_0a434bb9b883112a.png': 2, 'session_anchor:session_anchor_replay_5475493d35b3f719.png': 32, 'session_anchor:session_anchor_20260703_155058_b46bd348749c2ed5.png': 25, 'session_anchor:session_anchor_20260704_130602_f973615d792637b9.png': 4}

> **B-coverage: includes R4.** At least one B OWN_KILL was carried by an R4 session anchor (session_anchor:session_anchor_20260703_075738_b0b9f31a24bb1e98.png, session_anchor:session_anchor_20260703_130045_d9b52b6054b0f699.png, session_anchor:session_anchor_20260703_131828_c7dd3b58985cbd6c.png, session_anchor:session_anchor_20260703_133007_0fe744907416e4c6.png, session_anchor:session_anchor_20260703_141526_5ec2595697e0aa6b.png, session_anchor:session_anchor_20260703_141526_8e65da13b760735e.png, session_anchor:session_anchor_20260703_155058_b46bd348749c2ed5.png, session_anchor:session_anchor_20260703_162507_f2517c9d99b348b2.png, session_anchor:session_anchor_20260703_232037_bd0f6fc026ff3957.png, session_anchor:session_anchor_20260704_091615_0a434bb9b883112a.png, session_anchor:session_anchor_20260704_130602_f973615d792637b9.png, session_anchor:session_anchor_brval_66d7482992a0fff6.png, session_anchor:session_anchor_replay2_280a1f1513688989.png, session_anchor:session_anchor_replay_39767eb130325aa4.png, session_anchor:session_anchor_replay_51a7237c4f00ae45.png, session_anchor:session_anchor_replay_5475493d35b3f719.png, session_anchor:session_anchor_replay_b0b9f31a24bb1e98.png) — A-B agreement corroborates independence over that covered subset.

## Correlated blind spot (honest limit)
- Crops neither instrument resolved (UNRESOLVED by BOTH): **107** — the deep tail where feed_v1 < 0.40 (A cannot locate) AND template < 0.66 (B sub-floor). This is the human_oracle contact-sheet input.
