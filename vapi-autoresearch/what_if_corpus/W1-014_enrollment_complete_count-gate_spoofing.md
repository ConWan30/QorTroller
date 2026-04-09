# W1: enrollment_complete count-gate spoofing


### W1-014: enrollment_complete count-gate spoofing (Phase 166, Wiki-Generated)

**Status**: OPEN
**Detected by**: Skill 14 PostCode Sweep / vapi_wiki.py
**Phase**: Phase 166
**Timestamp**: 2026-04-08T01:15:22.718001+00:00

**Failure mechanism**: enrollment_complete fires on session COUNT=10 without biometric quality gate -- 10 non-standard sessions could cascade into TournamentActivationChainAgent

**Implication**: [Claude Code: what fails if unmitigated?]

**Mitigation**: require defensible=True from separation_defensibility_log as prerequisite (Phase 157 target)

**Invariants affected**: [Claude Code: list which of the frozen values are at risk]

**Separation ratio impact**: [Claude Code: None / Low / Medium / High]

[VAPI:Phase166:vapi_wiki.py:MEASURED]
