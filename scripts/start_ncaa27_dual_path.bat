@echo off
REM Default dual-path grind start (locked 2026-08-02).
REM See docs\runbook\NEXT_SESSION_FIRST.md
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_ncaa27_dual_path.ps1" %*
