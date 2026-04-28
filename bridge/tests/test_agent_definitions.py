"""Phase O0 Stream 5-prep Session 1 — agent definition + DID template parseability tests.

Per Decision C4: minimal parseability tests prevent malformed YAML or
JSON-LD from landing. Six tests verify file existence, frontmatter
parseability, JSON validity, required Pass 2C Section 6.1 fields, and
the modelClass field per Q8.

Tests:
  T-AGENT-1: vapi-anchor-sentry.md exists; YAML frontmatter parses
             cleanly; required keys present (name, description, tools).
  T-AGENT-2: vapi-guardian.md exists; YAML frontmatter parses cleanly;
             required keys present.
  T-AGENT-3: vapi-anchor-sentry.did.template.json is valid JSON.
  T-AGENT-4: vapi-guardian.did.template.json is valid JSON.
  T-AGENT-5: both DID templates contain the required Pass 2C 6.1 fields
             (@context, id, controller, verificationMethod, service,
             metadata).
  T-AGENT-6: both DID templates contain metadata.modelClass per Q8 with
             the literal value "claude-sonnet-4-6".
"""
import json
import os
import re

import pytest
import yaml


# Repo root resolved relative to this test file (bridge/tests/ → repo root).
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_AGENTS_DIR = os.path.join(_REPO_ROOT, ".claude", "agents")
_DID_TEMPLATES_DIR = os.path.join(_REPO_ROOT, "agents", "did_templates")


def _read_md_with_frontmatter(path: str) -> "tuple[dict, str]":
    """Parse a Claude Code agent definition file (.md with YAML frontmatter).

    Returns (frontmatter_dict, body_text). Raises ValueError on missing
    or malformed frontmatter.
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Frontmatter delimited by --- on its own line at start and after YAML.
    m = re.match(
        r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, flags=re.DOTALL,
    )
    if not m:
        raise ValueError(f"file does not start with YAML frontmatter: {path}")
    frontmatter_yaml = m.group(1)
    body = m.group(2)
    fm = yaml.safe_load(frontmatter_yaml)
    if not isinstance(fm, dict):
        raise ValueError(f"frontmatter is not a YAML mapping: {path}")
    return (fm, body)


# ---------------------------------------------------------------------------
# T-AGENT-1
# ---------------------------------------------------------------------------

def test_t_agent_1_sentry_definition_parses():
    """vapi-anchor-sentry.md exists; frontmatter parses; required keys
    present (name, description, tools).
    """
    path = os.path.join(_AGENTS_DIR, "vapi-anchor-sentry.md")
    assert os.path.isfile(path), f"missing agent file: {path}"
    fm, body = _read_md_with_frontmatter(path)
    assert fm["name"] == "vapi-anchor-sentry"
    assert isinstance(fm["description"], str) and fm["description"]
    assert "tools" in fm
    # Tools is a comma-separated string in Claude Code frontmatter.
    tools_str = fm["tools"]
    assert isinstance(tools_str, str)
    tools = [t.strip() for t in tools_str.split(",")]
    # Per Decision C3: read-only Phase O0 baseline.
    for required in ("Read", "Glob", "Grep", "WebFetch", "WebSearch"):
        assert required in tools, (
            f"required Phase O0 tool {required} missing from sentry: {tools}"
        )
    # Excluded tools must NOT appear (Decision C3 fail-closed).
    for excluded in ("Bash", "Write", "Edit", "NotebookEdit"):
        assert excluded not in tools, (
            f"excluded tool {excluded} present in sentry: {tools}"
        )
    # Body is non-trivial (contains the system prompt)
    assert len(body) > 200, "system prompt body suspiciously short"


# ---------------------------------------------------------------------------
# T-AGENT-2
# ---------------------------------------------------------------------------

def test_t_agent_2_guardian_definition_parses():
    """vapi-guardian.md mirror of T-AGENT-1."""
    path = os.path.join(_AGENTS_DIR, "vapi-guardian.md")
    assert os.path.isfile(path), f"missing agent file: {path}"
    fm, body = _read_md_with_frontmatter(path)
    assert fm["name"] == "vapi-guardian"
    assert isinstance(fm["description"], str) and fm["description"]
    tools = [t.strip() for t in fm["tools"].split(",")]
    for required in ("Read", "Glob", "Grep", "WebFetch", "WebSearch"):
        assert required in tools
    for excluded in ("Bash", "Write", "Edit", "NotebookEdit"):
        assert excluded not in tools
    assert len(body) > 200


# ---------------------------------------------------------------------------
# T-AGENT-3
# ---------------------------------------------------------------------------

def test_t_agent_3_sentry_did_template_valid_json():
    """vapi-anchor-sentry.did.template.json parses as valid JSON."""
    path = os.path.join(
        _DID_TEMPLATES_DIR, "vapi-anchor-sentry.did.template.json",
    )
    assert os.path.isfile(path), f"missing DID template: {path}"
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)  # raises json.JSONDecodeError if invalid
    assert isinstance(doc, dict)


# ---------------------------------------------------------------------------
# T-AGENT-4
# ---------------------------------------------------------------------------

def test_t_agent_4_guardian_did_template_valid_json():
    """vapi-guardian.did.template.json parses as valid JSON."""
    path = os.path.join(
        _DID_TEMPLATES_DIR, "vapi-guardian.did.template.json",
    )
    assert os.path.isfile(path), f"missing DID template: {path}"
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    assert isinstance(doc, dict)


# ---------------------------------------------------------------------------
# T-AGENT-5
# ---------------------------------------------------------------------------

def test_t_agent_5_did_templates_required_pass_2c_fields():
    """Both DID templates contain the required Pass 2C 6.1 fields:
    @context, id, controller, verificationMethod, service, metadata.
    """
    for name in ("vapi-anchor-sentry", "vapi-guardian"):
        path = os.path.join(_DID_TEMPLATES_DIR, f"{name}.did.template.json")
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        for required in (
            "@context", "id", "controller", "verificationMethod",
            "service", "metadata",
        ):
            assert required in doc, (
                f"required Pass 2C 6.1 field {required} missing from {name}"
            )
        # @context is the W3C DID context per Pass 2C line 1026
        assert doc["@context"] == ["https://www.w3.org/ns/did/v1"], (
            f"@context divergence in {name}: {doc['@context']}"
        )
        # verificationMethod has at least one entry of correct type
        vm = doc["verificationMethod"]
        assert isinstance(vm, list) and len(vm) >= 1
        assert vm[0]["type"] == "EcdsaSecp256k1VerificationKey2019"
        # service has at least one entry pointing to GitHub Apps
        svc = doc["service"]
        assert isinstance(svc, list) and len(svc) >= 1
        assert svc[0]["type"] == "VAPIOperatorAgent"
        assert (
            f"https://github.com/apps/{name}" in svc[0]["serviceEndpoint"]
        ), f"service endpoint mismatch in {name}: {svc[0]['serviceEndpoint']}"


# ---------------------------------------------------------------------------
# T-AGENT-6
# ---------------------------------------------------------------------------

def test_t_agent_6_did_templates_modelclass_q8():
    """Both DID templates contain metadata.modelClass with the literal
    value "claude-sonnet-4-6" per Pass 2C Q8 (operator approved
    2026-04-27).
    """
    for name in ("vapi-anchor-sentry", "vapi-guardian"):
        path = os.path.join(_DID_TEMPLATES_DIR, f"{name}.did.template.json")
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        meta = doc["metadata"]
        assert "modelClass" in meta, (
            f"metadata.modelClass missing from {name} (Pass 2C Q8 violation)"
        )
        assert meta["modelClass"] == "claude-sonnet-4-6", (
            f"modelClass divergence in {name}: {meta['modelClass']!r} "
            f"(Pass 2C Q8 commits to 'claude-sonnet-4-6')"
        )
        # Other Pass 2C 6.1 metadata fields
        assert meta["agentRole"] in ("AnchorSentry", "Guardian"), (
            f"agentRole unexpected in {name}: {meta.get('agentRole')!r}"
        )
        assert meta["vapiPhase"] == "O0"
