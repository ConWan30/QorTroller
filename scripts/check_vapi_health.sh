#!/bin/bash
# ============================================================
# VAPI Core Health Check — must always pass
# Run this before every commit during sub-protocol development.
# If this fails, nothing else proceeds — fix VAPI first.
# ============================================================
set -e
echo "Running VAPI core health check (bridge/ tests only)..."
pytest bridge/ -v --tb=short
echo "VAPI core health check PASSED"
