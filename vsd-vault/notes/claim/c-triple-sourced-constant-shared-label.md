---
type: claim
id: c-triple-sourced-constant-shared-label
title: N>=30 gate is triple-sourced (config field dead); player-label scoping not identity
created: 2026-06-30T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 12
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["i-fcert007-followup-report"]
---

Two findings in one (both from [[i-fcert007-followup-report]] anomalies 2 and 4):

1. The N>=30 developer gate exists as **three uncoordinated literals** — `enroll --min-n` default (`:47`),
   `single_subject_reflex_model(min_n=30)` default (`poep_calibration.py:92`), and the **dead**
   `config.developer_self_cert_min_reflex_n=30` (`config.py:2064`, unconsumed). The operator-facing config
   field that *looks* canonical is the one not wired; changing it would silently do nothing.

2. `single_subject_reflex_model` scopes the band by `player`-label string (default `"DEV"`), **not by
   identity**. Two developers both defaulting to `"DEV"` would pool into one band and one machine-global
   verdict file (`~/.vapi/poep_session_verdict.json`), with no identity binding to distinguish them.
   Isolation depends on the operator choosing a distinct label.
