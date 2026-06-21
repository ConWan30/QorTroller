"""Adversarial validation harness for the L9 x Trio-Retina consistency fusion.

RESEARCH ONLY. Runs the doc's section-5 experiment on SYNTHETIC, parameterised
data. Tells us how the fusion behaves as a function of the retina-axis unknowns;
does NOT prove real-world separation (that is Phase 2, real capture). Standalone:
imports nothing from ``bridge/``; gates nothing; no DB / FROZEN / PoAC touch.
"""
