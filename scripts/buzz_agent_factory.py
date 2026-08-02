#!/usr/bin/env python3
"""
buzz_agent_factory.py — Agentic creation for the QorTroller Buzz plane.

This script lets an authorized parent agent create:
  1. New channels (`create-channel`).
  2. New child agents (`create-agent`) — fresh nsec, kind 0 profile, `.env` file.
  3. New projects (`create-project`) — Buzz channel + NIP-34 git repo.
  4. New workflows (`create-workflow`) — Buzz channel + executable workflow.
  5. New templates (`create-template`) — NIP-23 long-form note.
  6. Brainstorm seeds (`brainstorm`) — post to a brainstorm channel.

Authority model:
  - Parent provides `BUZZ_PRIVATE_KEY` (its own key).
  - Optional `BUZZ_LOBBY_CHANNEL_ID` / `BUZZ_AUDIT_CHANNEL_ID` / `BUZZ_BRAINSTORM_CHANNEL_ID`.
  - No limit on children unless the caller imposes one.

Usage:
  $env:BUZZ_PRIVATE_KEY = "nsec1..."
  $env:BUZZ_RELAY_URL = "wss://qortroller.communities.buzz.xyz"
  python scripts/buzz_agent_factory.py create-project --name "MyProject" --description "Expand QorTroller"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
AGENTS_DIR.mkdir(parents=True, exist_ok=True)

VALID_CLAUSES = {"P-SOV", "P-ATT", "P-VSS", "P-WMP", "P-OPS", "P-FRM", "P-STU"}
AGENT_ROSTER_CHANNEL_ID = os.environ.get("BUZZ_AGENT_ROSTER_CHANNEL_ID", "")
FRAMEWORKS_CHANNEL_ID = os.environ.get("BUZZ_FRAMEWORKS_CHANNEL_ID", "")


def _registry_path() -> Path:
    return REPO_ROOT / "agents" / "registry.json"


def _load_registry() -> dict:
    path = _registry_path()
    if not path.exists():
        return {"version": "1.0.0", "roster": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] could not load registry: {e}", file=sys.stderr)
        return {"version": "1.0.0", "roster": []}


def _save_registry(registry: dict) -> None:
    _registry_path().write_text(json.dumps(registry, indent=2), encoding="utf-8")


def _raw_to_http(url: str) -> str:
    if url.startswith("ws://"):
        return "http://" + url[len("ws://"):]
    if url.startswith("wss://"):
        return "https://" + url[len("wss://"):]
    return url


def _raw_to_ws(url: str) -> str:
    if url.startswith("http://"):
        return "ws://" + url[len("http://"):]
    if url.startswith("https://"):
        return "wss://" + url[len("https://"):]
    return url


def _relay_host(url: str) -> str:
    return _raw_to_http(url).replace("http://", "").replace("https://", "").rstrip("/")


def _safe_id(name: str) -> str:
    """Slugify a display name into a Buzz-safe repo/note id."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name).strip("-").lower()
    slug = re.sub(r"-+", "-", slug)
    return slug[:64] or "artifact"


def _safe_slug(name: str) -> str:
    """Slugify for note slugs (lowercase only)."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:80] or "template"


def _safe_step_id(name: str, idx: int) -> str:
    """Make a workflow step id that passes buzz-workflow validation."""
    sid = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()[:64] or f"step_{idx}"
    if sid and sid[0].isdigit():
        sid = "s_" + sid
    sid = re.sub(r"[^a-zA-Z0-9_]", "_", sid)
    return sid[:64] or f"step_{idx}"


def _cli_path() -> str:
    env = os.environ.get("BUZZ_CLI_PATH", "")
    if env and os.path.isfile(env):
        return env
    default = str(REPO_ROOT / "buzz" / "target" / "debug" / "buzz.exe")
    if os.path.isfile(default):
        return default
    return env or default


def _helper_path() -> str:
    env = os.environ.get("BUZZ_HELPER_PATH", "")
    if env and os.path.isfile(env):
        return env
    default = str(REPO_ROOT / "buzz" / "target" / "debug" / "qortroller-buzz.exe")
    if os.path.isfile(default):
        return default
    return env or default


def _buzz_cli(args: list[str], extra_env: Optional[dict] = None, timeout: float = 30) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = _raw_to_http(env.get("BUZZ_RELAY_URL", "http://localhost:3000"))
    if extra_env:
        env.update(extra_env)
    try:
        result = subprocess.run(
            [_cli_path()] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            shell=False,
            cwd=REPO_ROOT,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def _qortroller_buzz(args: list[str], stdin: str = "", extra_env: Optional[dict] = None, timeout: float = 30) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["BUZZ_RELAY_URL"] = _raw_to_ws(env.get("BUZZ_RELAY_URL", "ws://localhost:3000"))
    env.pop("BUZZ_AUTH_TAG", None)
    if extra_env:
        env.update(extra_env)
    try:
        result = subprocess.run(
            [_helper_path()] + args,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            shell=False,
            cwd=REPO_ROOT,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def _my_npub(private_key: str) -> str:
    try:
        from nostr_sdk import Keys
        return Keys.parse(private_key).public_key().to_bech32()
    except Exception as e:
        print(f"[!] could not derive npub: {e}", file=sys.stderr)
        return ""


def _my_hex(private_key: str) -> str:
    try:
        from nostr_sdk import Keys
        return Keys.parse(private_key).public_key().to_hex()
    except Exception as e:
        print(f"[!] could not derive hex pubkey: {e}", file=sys.stderr)
        return ""


def _validate_clause(clause: str) -> bool:
    if clause in VALID_CLAUSES:
        return True
    print(f"[!] invalid clause '{clause}'. Valid: {', '.join(sorted(VALID_CLAUSES))}", file=sys.stderr)
    return False


def _parse_resume(resume_input: str) -> dict:
    """Parse a resume from a JSON string or a file path."""
    if not resume_input:
        return {}
    if Path(resume_input).exists():
        try:
            return json.loads(Path(resume_input).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[!] could not read resume file: {e}", file=sys.stderr)
            return {}
    try:
        return json.loads(resume_input)
    except Exception:
        # Try simple key:value semicolon syntax: "competence: a,b; forbidden: x,y"
        resume = {}
        for part in resume_input.split(";"):
            if ":" in part:
                key, value = part.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key in ("competence", "forbidden", "channels", "tools"):
                    resume[key] = [v.strip() for v in value.split(",") if v.strip()]
                else:
                    resume[key] = value
        return resume


def _default_forbidden() -> list[str]:
    return ["keys", "shell", "chain", "VSS OPEN", "claim inflation", "silent topology"]


def _generate_key() -> tuple[str, str]:
    """Generate (nsec, npub) for a new child agent."""
    try:
        from nostr_sdk import Keys
        keys = Keys.generate()
        nsec = keys.secret_key().to_bech32()
        npub = keys.public_key().to_bech32()
        return nsec, npub
    except Exception as e:
        print(f"[!] key generation failed: {e}", file=sys.stderr)
        sys.exit(1)


def _write_child_env(name: str, nsec: str, npub: str, relay_url: str, role: str, parent_npub: str) -> Path:
    env_path = AGENTS_DIR / f"{name}.env"
    env_text = f"""# Child agent env for {name} — generated by buzz_agent_factory.py
# DO NOT COMMIT. Keep this secret.
BUZZ_PRIVATE_KEY={nsec}
BUZZ_RELAY_URL={relay_url}
BUZZ_PERSONAL_AGENT_NAME={name}
BUZZ_PERSONAL_AGENT_ABOUT=Child QorTroller agent ({role}) minted by {parent_npub}.
BUZZ_PERSONAL_AGENT_ENABLED=0
# Set BUZZ_LOBBY_CHANNEL_ID and BUZZ_PERSONAL_AGENT_DM_IDS, then enable.
"""
    env_path.write_text(env_text, encoding="utf-8")
    return env_path


def _post_artifact(
    name: str,
    artifact_type: str,
    channel_id: str,
    extra_tags: list[list[str]],
    content: str,
) -> bool:
    """Post a genesis message for an artifact into a channel."""
    payload = json.dumps({
        "channel": channel_id,
        "content": content,
        "tags": [
            ["qortroller", "1"],
            ["artifact", artifact_type],
            ["artifact_name", name],
        ] + extra_tags,
    })
    rc, stdout, stderr = _qortroller_buzz(["publish"], stdin=payload, timeout=30)
    if rc != 0:
        print(f"[!] {artifact_type} genesis post failed: {stderr}", file=sys.stderr)
        return False
    try:
        data = json.loads(stdout)
        return data.get("accepted", False)
    except Exception:
        return False


def create_channel(name: str, description: str, visibility: str) -> Optional[str]:
    """Create a channel with the parent key. Returns channel_id or None."""
    args = ["channels", "create", "--name", name, "--type", "stream", "--visibility", visibility]
    if description:
        args += ["--description", description]

    rc, stdout, stderr = _buzz_cli(args)
    if rc != 0:
        print(f"[!] channel create failed: {stderr}", file=sys.stderr)
        return None
    try:
        data = json.loads(stdout)
        channel_id = data.get("channel_id")
        print(f"[*] channel created: {channel_id}")
        return channel_id
    except Exception:
        print(f"[!] could not parse channel response: {stdout}", file=sys.stderr)
        return None


def create_project(name: str, description: str, goal: str, channel_id: Optional[str] = None) -> Optional[dict]:
    """Create a project: a Buzz channel + a NIP-34 git repo announcement."""
    parent_key = os.environ.get("BUZZ_PRIVATE_KEY", "")
    parent_npub = _my_npub(parent_key)
    relay_url = os.environ.get("BUZZ_RELAY_URL", "wss://qortroller.communities.buzz.xyz")
    relay_host = _relay_host(relay_url)
    repo_id = _safe_id(name)
    display_name = name
    desc = description or goal or f"{name} project for QorTroller"
    if goal:
        desc = f"{desc} | Goal: {goal}"
    clone_url = f"https://{relay_host}/git/{_my_hex(parent_key)}/{repo_id}"
    ws_url = _raw_to_ws(relay_url)

    if not channel_id:
        channel_id = create_channel(name, desc, "open")
    if not channel_id:
        return None

    repo_args = [
        "repos", "create",
        "--id", repo_id,
        "--name", display_name,
        "--description", desc,
        "--clone", clone_url,
        "--nostr-relay", ws_url,
    ]
    repo_rc, repo_out, repo_err = _buzz_cli(repo_args, timeout=60)
    if repo_rc != 0:
        print(f"[!] repo create failed: {repo_err}", file=sys.stderr)
        return {"channel_id": channel_id, "name": name, "type": "project", "error": repo_err}
    try:
        repo_data = json.loads(repo_out)
        event_id = repo_data.get("event_id")
    except Exception:
        event_id = None

    content = f'Project "{name}" repo: {clone_url}\nGoal: {goal or desc}'
    if event_id:
        content += f"\nRepo event: {event_id}"
    _post_artifact(
        name, "project", channel_id,
        [["repo_id", repo_id], ["clone", clone_url]],
        content,
    )
    return {
        "channel_id": channel_id,
        "repo_id": repo_id,
        "clone_url": clone_url,
        "event_id": event_id,
        "name": name,
        "type": "project",
    }


def create_workflow(name: str, description: str, steps: str, channel_id: Optional[str] = None) -> Optional[dict]:
    """Create a workflow: a Buzz channel + an executable workflow definition."""
    if not channel_id:
        channel_id = create_channel(name, description, "open")
    if not channel_id:
        return None

    step_lines = [s.strip() for s in (steps or "").split(",") if s.strip()] or ["notify team"]
    safe_desc = description or name
    try:
        import json as _json
        yaml_lines = [
            f"name: {_json.dumps(name)}",
            f"description: {_json.dumps(safe_desc)}",
            "trigger:",
            "  on: message_posted",
            "steps:",
        ]
        for i, s in enumerate(step_lines):
            sid = _safe_step_id(s, i)
            text = s if len(s) <= 500 else s[:497] + "..."
            yaml_lines.append(f"  - id: {sid}")
            yaml_lines.append("    action: send_message")
            yaml_lines.append(f"    text: {_json.dumps(text)}")
        yaml = "\n".join(yaml_lines)
    except Exception as e:
        print(f"[!] workflow YAML build failed: {e}", file=sys.stderr)
        return None

    rc, stdout, stderr = _buzz_cli(["workflows", "create", "--channel", channel_id, "--yaml", yaml], timeout=60)
    if rc != 0:
        print(f"[!] workflow create failed: {stderr}", file=sys.stderr)
        return {"channel_id": channel_id, "name": name, "type": "workflow", "error": stderr}
    try:
        data = json.loads(stdout)
        workflow_id = data.get("workflow_id")
    except Exception:
        workflow_id = None

    content = f'Workflow "{name}":\n' + "\n".join(f"{i+1}. {s}" for i, s in enumerate(step_lines))
    _post_artifact(
        name, "workflow", channel_id,
        [["workflow_id", workflow_id or ""], ["steps", ",".join(step_lines)]],
        content,
    )
    return {
        "channel_id": channel_id,
        "name": name,
        "type": "workflow",
        "workflow_id": workflow_id,
        "steps": step_lines,
    }


def create_template(name: str, description: str, source: str) -> Optional[dict]:
    """Create a template as a NIP-23 long-form note."""
    slug = _safe_slug(name)
    title = name
    body_lines = [description or f"Reusable QorTroller template for {name}."]
    if source:
        body_lines.append(f"Source/seed: {source}")
    body = "\n".join(body_lines)

    rc, stdout, stderr = _buzz_cli([
        "notes", "set",
        "--name", slug,
        "--title", title,
        "--summary", description or f"Template: {name}",
        "--content", body,
        "--tag", "qortroller",
        "--tag", "template",
    ], timeout=60)
    if rc != 0:
        print(f"[!] template note failed: {stderr}", file=sys.stderr)
        return None

    naddr = None
    for line in stdout.splitlines():
        if line.lower().startswith("naddr"):
            parts = line.split(None, 1)
            if len(parts) > 1:
                naddr = parts[1].strip()
    return {
        "slug": slug,
        "naddr": naddr,
        "name": name,
        "type": "template",
        "source": source or "manual",
    }


def brainstorm(topic: str, channel_id: str) -> bool:
    """Post a brainstorming seed to a brainstorm channel."""
    if not channel_id:
        print("[!] no brainstorm channel configured", file=sys.stderr)
        return False
    content = f"Brainstorm: {topic}. What novel QorTroller implementations or integrations could this unlock?"
    return _post_artifact(topic, "brainstorm", channel_id, [], content)


def hire_agent(name: str, clause: str, resume: str, supervisor: str = "operator", about: str = "", post_birth: bool = True, approved: bool = False) -> Optional[dict]:
    """Hire a child agent: validate clause/resume, generate key, write .env, set profile, announce."""
    if not _validate_clause(clause):
        return None

    resume_data = _parse_resume(resume)
    forbidden = resume_data.get("forbidden") or _default_forbidden()
    competence = resume_data.get("competence", [])
    if not competence:
        print("[!] resume must include 'competence'", file=sys.stderr)
        return None

    parent_key = os.environ.get("BUZZ_PRIVATE_KEY", "")
    if not parent_key:
        print("[!] BUZZ_PRIVATE_KEY required (parent key)", file=sys.stderr)
        return None

    parent_npub = _my_npub(parent_key)
    if not parent_npub:
        return None

    nsec, npub = _generate_key()
    relay_url = os.environ.get("BUZZ_RELAY_URL", "wss://qortroller.communities.buzz.xyz")
    env_path = _write_child_env(name, nsec, npub, relay_url, clause, parent_npub)
    print(f"[*] child agent key written to {env_path}")

    child_about = about or f"QorTroller agent ({clause}) hired by {parent_npub}."
    extra_env = {
        "BUZZ_PRIVATE_KEY": nsec,
        "BUZZ_RELAY_URL": relay_url,
    }
    rc, _, stderr = _buzz_cli(["users", "set-profile", "--name", name, "--about", child_about], extra_env=extra_env, timeout=30)
    if rc != 0:
        print(f"[!] child profile set failed (child may need relay invite): {stderr}", file=sys.stderr)
    else:
        print(f"[*] child profile set for {npub}")

    agent_id = _safe_id(name)
    registry = _load_registry()
    registry.setdefault("roster", []).append({
        "agent_id": agent_id,
        "display_name": name,
        "npub": npub,
        "hex": _my_hex(nsec),
        "clause": clause,
        "parent": "operator",
        "supervisor": supervisor,
        "status": "hired" if approved else "candidate",
        "competence": competence,
        "evidence_bar": resume_data.get("evidence_bar", ""),
        "forbidden": forbidden,
        "channels": resume_data.get("channels", []),
        "tools": resume_data.get("tools", []),
        "output_types": resume_data.get("output_types", ["digest"]),
        "env_path": str(env_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sealed_by": parent_npub,
    })
    _save_registry(registry)
    print(f"[*] registry updated: {agent_id} ({'hired' if approved else 'candidate'})")

    roster_channel = AGENT_ROSTER_CHANNEL_ID or os.environ.get("BUZZ_AUDIT_CHANNEL_ID", "")
    if post_birth and roster_channel:
        birth_content = f"Agent {'hired' if approved else 'proposed'}: {name} ({clause}) by {parent_npub} → child {npub}\nCompetence: {', '.join(competence)}\nForbidden: {', '.join(forbidden)}"
        payload = json.dumps({
            "channel": roster_channel,
            "content": birth_content,
            "tags": [
                ["qortroller", "1"],
                ["agent_mint", "1"],
                ["agent_name", name],
                ["agent_clause", clause],
                ["parent", parent_npub],
                ["child", npub],
            ],
        })
        rc, stdout, stderr = _qortroller_buzz(["publish"], stdin=payload, timeout=30)
        if rc != 0:
            print(f"[!] roster post failed: {stderr}", file=sys.stderr)
        else:
            try:
                data = json.loads(stdout)
                if data.get("accepted"):
                    print(f"[*] roster post accepted")
            except Exception:
                pass

    return {
        "nsec": nsec,
        "npub": npub,
        "name": name,
        "clause": clause,
        "competence": competence,
        "parent_npub": parent_npub,
        "env_path": str(env_path),
        "status": "hired" if approved else "candidate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def propose(
    artifact: str,
    name: str,
    clause: str,
    description: str = "",
    goal: str = "",
    steps: str = "",
    source: str = "",
    topic: str = "",
) -> Optional[dict]:
    """Post a proposal to #frameworks for a channel, project, workflow, template, or brainstorm."""
    if not _validate_clause(clause):
        return None

    parent_key = os.environ.get("BUZZ_PRIVATE_KEY", "")
    parent_npub = _my_npub(parent_key) or "unknown"
    frameworks_channel = FRAMEWORKS_CHANNEL_ID or os.environ.get("BUZZ_FRAMEWORKS_CHANNEL_ID", "")
    if not frameworks_channel:
        print("[!] no #frameworks channel configured (BUZZ_FRAMEWORKS_CHANNEL_ID)", file=sys.stderr)
        return None

    details = []
    if description:
        details.append(f"Description: {description}")
    if goal:
        details.append(f"Goal: {goal}")
    if steps:
        details.append(f"Steps: {steps}")
    if source:
        details.append(f"Source: {source}")
    if topic:
        details.append(f"Topic: {topic}")

    content = f"Proposal: {artifact} `{name}`\nClause: {clause}\nProposed by: {parent_npub}\n"
    if details:
        content += "\n" + "\n".join(details)
    content += "\n\nReply with `approve` or post a WP skeleton to move to Ops."

    extra_tags = [
        ["proposal", artifact],
        ["artifact_name", name],
        ["clause", clause],
    ]
    ok = _post_artifact(name, "proposal", frameworks_channel, extra_tags, content)
    if not ok:
        return None
    return {
        "artifact": artifact,
        "name": name,
        "clause": clause,
        "proposed_by": parent_npub,
        "status": "proposed",
    }


def propose_wp(
    topic: str,
    clause: str,
    problem: str,
    non_claims: str,
    acceptance: str,
    parent_proposal: str = "",
) -> Optional[dict]:
    """Post a WP skeleton to #frameworks."""
    if not _validate_clause(clause):
        return None

    parent_key = os.environ.get("BUZZ_PRIVATE_KEY", "")
    parent_npub = _my_npub(parent_key) or "unknown"
    frameworks_channel = FRAMEWORKS_CHANNEL_ID or os.environ.get("BUZZ_FRAMEWORKS_CHANNEL_ID", "")
    if not frameworks_channel:
        print("[!] no #frameworks channel configured", file=sys.stderr)
        return None

    content = f"WP Skeleton: {topic}\nClause: {clause}\nAuthor: {parent_npub}\n\n"
    content += f"## Problem\n{problem}\n\n"
    content += f"## Non-claims / honesty ceiling\n{non_claims}\n\n"
    content += f"## Acceptance tests / exit criteria\n{acceptance}\n\n"
    if parent_proposal:
        content += f"Parent proposal: {parent_proposal}\n\n"
    content += "Handoff: Frame → Ops → Seal. Human seal required."

    extra_tags = [
        ["wp", "1"],
        ["topic", topic],
        ["clause", clause],
    ]
    if parent_proposal:
        extra_tags.append(["parent_proposal", parent_proposal])

    ok = _post_artifact(topic, "wp", frameworks_channel, extra_tags, content)
    if not ok:
        return None
    return {
        "topic": topic,
        "clause": clause,
        "author": parent_npub,
        "status": "framed",
    }


def _creation_approved() -> bool:
    return os.environ.get("BUZZ_CREATION_APPROVED", "") == "1" or os.environ.get("BUZZ_MINTERS") == "1"


def _add_clause_and_approve(parser):
    parser.add_argument("--clause", default="", help="Purpose clause (P-SOV, P-ATT, P-VSS, P-WMP, P-OPS, P-FRM, P-STU)")
    parser.add_argument("--approve", action="store_true", help="Skip proposal and mint immediately (operator-only)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Agentic factory for QorTroller Buzz.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ch = sub.add_parser("create-channel", help="Create or propose a new channel")
    ch.add_argument("--name", required=True)
    ch.add_argument("--description", default="")
    ch.add_argument("--visibility", default="open", choices=["open", "restricted"])
    _add_clause_and_approve(ch)

    ag = sub.add_parser("create-agent", help="Hire a child agent (v1: use 'hire' instead)")
    ag.add_argument("--name", required=True)
    ag.add_argument("--role", default="concierge")
    ag.add_argument("--about", default="")
    ag.add_argument("--clause", default="", help="Purpose clause for the agent")
    ag.add_argument("--resume", default="", help="Resume JSON string or file path")
    ag.add_argument("--no-birth-post", action="store_true", help="Skip roster birth post")

    pr = sub.add_parser("create-project", help="Create or propose a project")
    pr.add_argument("--name", required=True)
    pr.add_argument("--description", default="")
    pr.add_argument("--goal", default="")
    pr.add_argument("--channel", default="", help="Optional existing channel UUID")
    _add_clause_and_approve(pr)

    wf = sub.add_parser("create-workflow", help="Create or propose a workflow")
    wf.add_argument("--name", required=True)
    wf.add_argument("--description", default="")
    wf.add_argument("--steps", default="")
    wf.add_argument("--channel", default="", help="Optional existing channel UUID")
    _add_clause_and_approve(wf)

    tp = sub.add_parser("create-template", help="Create or propose a template")
    tp.add_argument("--name", required=True)
    tp.add_argument("--description", default="")
    tp.add_argument("--source", default="")
    _add_clause_and_approve(tp)

    br = sub.add_parser("brainstorm", help="Post a brainstorm seed")
    br.add_argument("--topic", required=True)
    br.add_argument("--channel", default="", help="Brainstorm channel UUID (or BUZZ_BRAINSTORM_CHANNEL_ID)")
    _add_clause_and_approve(br)

    h = sub.add_parser("hire", help="Hire a child agent with clause and resume")
    h.add_argument("--name", required=True)
    h.add_argument("--clause", required=True)
    h.add_argument("--resume", required=True, help="Resume JSON or 'competence: a,b; forbidden: x,y' string")
    h.add_argument("--supervisor", default="operator")
    h.add_argument("--about", default="")
    h.add_argument("--approve", action="store_true", help="Hire immediately instead of candidate")
    h.add_argument("--no-roster-post", action="store_true")

    prop = sub.add_parser("propose", help="Propose a channel/project/workflow/template/brainstorm")
    prop.add_argument("--artifact", required=True, choices=["channel", "project", "workflow", "template", "brainstorm"])
    prop.add_argument("--name", required=True)
    prop.add_argument("--clause", required=True)
    prop.add_argument("--description", default="")
    prop.add_argument("--goal", default="")
    prop.add_argument("--steps", default="")
    prop.add_argument("--source", default="")
    prop.add_argument("--topic", default="")

    wp = sub.add_parser("propose-wp", help="Post a WP skeleton to #frameworks")
    wp.add_argument("--topic", required=True)
    wp.add_argument("--clause", required=True)
    wp.add_argument("--problem", required=True)
    wp.add_argument("--non-claims", required=True)
    wp.add_argument("--acceptance", required=True)
    wp.add_argument("--parent-proposal", default="")

    gpush = sub.add_parser("git-push", help="Push the current branch to a Buzz NIP-34 repo")
    gpush.add_argument("--repo", required=True, help="Repository name on Buzz (e.g. MyProject)")
    gpush.add_argument("--branch", default="main")
    gpush.add_argument("--owner-hex", default="", help="Owner pubkey hex (defaults to caller)")

    gcommit = sub.add_parser("git-commit", help="Stage, commit, and push to a Buzz NIP-34 repo")
    gcommit.add_argument("--repo", required=True)
    gcommit.add_argument("--message", required=True)
    gcommit.add_argument("--branch", default="main")
    gcommit.add_argument("--owner-hex", default="")

    gmerge = sub.add_parser("git-merge", help="Mark a Buzz PR as merged")
    gmerge.add_argument("--pr-event-id", required=True)

    gpro = sub.add_parser("git-pr-open", help="Open a Buzz pull request")
    gpro.add_argument("--repo", required=True)
    gpro.add_argument("--title", required=True)
    gpro.add_argument("--body", required=True)
    gpro.add_argument("--source", default="main")
    gpro.add_argument("--target", default="main")

    args = parser.parse_args()

    if not os.environ.get("BUZZ_PRIVATE_KEY") and args.cmd not in ("git-push", "git-commit", "git-merge", "git-pr-open"):
        print("[!] BUZZ_PRIVATE_KEY (parent key) is required", file=sys.stderr)
        return 1

    if args.cmd == "create-channel":
        if not args.clause:
            print("[!] create-channel requires --clause", file=sys.stderr)
            return 1
        if args.approve or _creation_approved():
            channel_id = create_channel(args.name, args.description, args.visibility)
            return 0 if channel_id else 1
        result = propose("channel", args.name, args.clause, description=args.description)
        if result:
            print(json.dumps(result, indent=2))
        return 0 if result else 1

    if args.cmd == "create-project":
        if not args.clause:
            print("[!] create-project requires --clause", file=sys.stderr)
            return 1
        if args.approve or _creation_approved():
            result = create_project(args.name, args.description, args.goal, channel_id=args.channel or None)
        else:
            result = propose("project", args.name, args.clause, description=args.description, goal=args.goal)
        if result:
            print(json.dumps(result, indent=2))
        return 0 if result else 1

    if args.cmd == "create-workflow":
        if not args.clause:
            print("[!] create-workflow requires --clause", file=sys.stderr)
            return 1
        if args.approve or _creation_approved():
            result = create_workflow(args.name, args.description, args.steps, channel_id=args.channel or None)
        else:
            result = propose("workflow", args.name, args.clause, description=args.description, steps=args.steps)
        if result:
            print(json.dumps(result, indent=2))
        return 0 if result else 1

    if args.cmd == "create-template":
        if not args.clause:
            print("[!] create-template requires --clause", file=sys.stderr)
            return 1
        if args.approve or _creation_approved():
            result = create_template(args.name, args.description, args.source)
        else:
            result = propose("template", args.name, args.clause, description=args.description, source=args.source)
        if result:
            print(json.dumps(result, indent=2))
        return 0 if result else 1

    if args.cmd == "brainstorm":
        if not args.clause:
            print("[!] brainstorm requires --clause", file=sys.stderr)
            return 1
        channel_id = args.channel or os.environ.get("BUZZ_BRAINSTORM_CHANNEL_ID", "")
        if not channel_id:
            print("[!] no brainstorm channel configured", file=sys.stderr)
            return 1
        if args.approve or _creation_approved():
            ok = brainstorm(args.topic, channel_id)
        else:
            result = propose("brainstorm", args.topic, args.clause, topic=args.topic)
            ok = bool(result)
        if ok:
            print(json.dumps({"topic": args.topic, "channel_id": channel_id, "status": "seeded"}, indent=2))
        return 0 if ok else 1

    if args.cmd == "create-agent":
        print("[!] create-agent is deprecated; use `hire --name <n> --clause P-... --resume ...`", file=sys.stderr)
        if not args.clause or not args.resume:
            return 1
        result = hire_agent(args.name, args.clause, args.resume, supervisor="operator", about=args.about, post_birth=not args.no_birth_post, approved=True)
        if result:
            print(json.dumps({k: v for k, v in result.items() if k != "nsec"}, indent=2))
            print(f"[*] child nsec stored in: {result['env_path']}")
            return 0
        return 1

    if args.cmd == "hire":
        result = hire_agent(args.name, args.clause, args.resume, supervisor=args.supervisor, about=args.about, post_birth=not args.no_roster_post, approved=args.approve)
        if result:
            print(json.dumps({k: v for k, v in result.items() if k != "nsec"}, indent=2))
            print(f"[*] child nsec stored in: {result['env_path']}")
            return 0
        return 1

    if args.cmd == "propose":
        result = propose(args.artifact, args.name, args.clause, description=args.description, goal=args.goal, steps=args.steps, source=args.source, topic=args.topic)
        if result:
            print(json.dumps(result, indent=2))
        return 0 if result else 1

    if args.cmd == "propose-wp":
        result = propose_wp(args.topic, args.clause, args.problem, args.non_claims, args.acceptance, parent_proposal=args.parent_proposal)
        if result:
            print(json.dumps(result, indent=2))
        return 0 if result else 1

    if args.cmd in ("git-push", "git-commit", "git-merge", "git-pr-open"):
        factory_cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "buzz_git.py"),
        ]
        if args.cmd == "git-push":
            factory_cmd += ["push", args.repo, args.branch]
        elif args.cmd == "git-commit":
            factory_cmd += ["commit", args.repo, args.message, args.branch]
        elif args.cmd == "git-merge":
            factory_cmd += ["merge", args.pr_event_id]
        elif args.cmd == "git-pr-open":
            factory_cmd += ["pr-open", args.repo, args.title, args.body]

        env = os.environ.copy()
        env["BUZZ_CLI_PATH"] = _cli_path()
        env["BUZZ_HELPER_PATH"] = _helper_path()
        env["BUZZ_RELAY_HTTP"] = _raw_to_http(os.environ.get("BUZZ_RELAY_URL", "wss://qortroller.communities.buzz.xyz"))
        try:
            result = subprocess.run(
                factory_cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=REPO_ROOT,
                env=env,
                shell=False,
            )
            if result.returncode == 0:
                print(result.stdout.strip())
                return 0
            print(f"[!] {args.cmd} failed:\n{result.stderr.strip()[:1000]}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"[!] {args.cmd} error: {e}", file=sys.stderr)
            return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
