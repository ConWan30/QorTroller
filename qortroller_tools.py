#!/usr/bin/env python3
"""
QorTroller tool engine
======================
ToolEngine (the 30+ inline engineering tools), extracted verbatim from
qortroller.py (third step of the monolith split; qortroller.py re-exports
it as a façade). Security invariant carried with the code: every shell
tool stays shell=False + shlex.split (rig_health's shell_false check
inspects this module).
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import os
import re
import shlex
import sqlite3
import subprocess
import sys
import time
import uuid
from typing import Any, Callable, Optional

REPO_ROOT = os.environ.get(
    "QORTROLLER_ROOT",
    os.path.dirname(os.path.abspath(__file__))
)

# Collaborators (injected by callers; imported for runtime references)
from qortroller_memory import MethodologyRegistry  # noqa: E402
from qortroller_clients import BridgeClient  # noqa: E402

# Governance-tools availability flag (mirrors qortroller.py's try/except import)
try:
    import _daemon_tools_schema  # noqa: F401
    _HAS_GOVERNANCE = True
except ImportError:
    _HAS_GOVERNANCE = False


# ═══════════════════════════════════════════════════════════════════════════════
#  TOOL ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ToolEngine:
    """All engineering tools available to the LLM. Each tool is a function
    that takes args and returns a string result."""

    def __init__(self, repo_root: str = REPO_ROOT,
                 bridge: Optional[BridgeClient] = None):
        self.repo_root = repo_root
        self.bridge = bridge or BridgeClient()
        self._tools_definition = self._build_tools_definition()

    def _build_tools_definition(self) -> list[dict]:
        """Build the OpenAI-compatible tool definitions for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file's contents. For large files, use read_file_range.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Relative path from repo root"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file_range",
                    "description": "Paginated read of large files. Returns numbered lines (1-indexed).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "offset": {"type": "integer", "description": "0-indexed line number to start"},
                            "limit": {"type": "integer", "description": "Number of lines (default 500, max 2000)"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Create or overwrite a file. Creates parent directories if needed.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Edit a file by finding and replacing text. The before text must match exactly.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "before": {"type": "string"},
                            "after": {"type": "string"}
                        },
                        "required": ["path", "before", "after"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": "Execute a shell command. For git, pytest, and system operations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "timeout_secs": {"type": "integer", "default": 30}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_pytest",
                    "description": "Run pytest on a test path. Returns exit code, summary, and failures.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "test_path": {"type": "string", "default": "bridge/tests/"},
                            "timeout": {"type": "integer", "default": 120},
                            "extra_args": {"type": "string", "default": ""}
                        },
                        "required": ["test_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_log",
                    "description": "Show recent git log.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "n": {"type": "integer", "default": 10}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_diff",
                    "description": "Show git diff (unstaged changes).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": ""}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Show git status.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_commit",
                    "description": "Stage all and commit with a message.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"}
                        },
                        "required": ["message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bridge_health",
                    "description": "Check if the bridge is running and healthy.",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bridge_get",
                    "description": "GET a bridge API endpoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "timeout": {"type": "integer", "default": 10}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "bridge_post",
                    "description": "POST to a bridge API endpoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "data": {"type": "object", "default": {}},
                            "timeout": {"type": "integer", "default": 30}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "methodology_query",
                    "description": "Query the methodology registry for lessons learned.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keywords": {"type": "string", "default": ""}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "methodology_add",
                    "description": "Add a new lesson to the methodology registry.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "failure_class": {"type": "string"},
                            "anti_pattern": {"type": "string"},
                            "correct_pattern": {"type": "string"},
                            "agent_commit": {"type": "string", "default": ""}
                        },
                        "required": ["failure_class", "anti_pattern", "correct_pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Search for files matching a pattern.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string", "default": "."}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "grep",
                    "description": "Search for text in files.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string", "default": "."},
                            "include": {"type": "string", "default": "*.py"}
                        },
                        "required": ["pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_invariants",
                    "description": "Check PV-CI invariants against the codebase.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "focus": {"type": "string", "default": ""}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_contradictions",
                    "description": "Check for FSCA contradictions from the bridge.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "protocol_state",
                    "description": "Get the current protocol state from the bridge.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "tree",
                    "description": "List directory tree with file sizes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": "."},
                            "depth": {"type": "integer", "default": 2}
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "hardware_status",
                    "description": "Check current hardware state (DualShock, capture card, bridge).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
        ]

    @property
    def tool_definitions(self) -> list[dict]:
        return self._tools_definition

    def execute(self, name: str, args: dict) -> str:
        """Execute a tool by name with given args."""
        handler = self._get_handler(name)
        if handler is None:
            return f"Error: unknown tool '{name}'"
        try:
            result = handler(**args)
            return str(result) if result is not None else "(no output)"
        except Exception as e:
            return f"Error executing {name}: {e}"

    def _get_handler(self, name: str) -> Optional[Callable]:
        handlers = {
            "read_file": self._read_file,
            "read_file_range": self._read_file_range,
            "write_file": self._write_file,
            "edit_file": self._edit_file,
            "shell": self._shell,
            "run_pytest": self._run_pytest,
            "git_log": self._git_log,
            "git_diff": self._git_diff,
            "git_status": self._git_status,
            "git_commit": self._git_commit,
            "bridge_health": self._bridge_health,
            "bridge_get": self._bridge_get,
            "bridge_post": self._bridge_post,
            "methodology_query": self._methodology_query,
            "methodology_add": self._methodology_add,
            "search_files": self._search_files,
            "grep": self._grep,
            "check_invariants": self._check_invariants,
            "check_contradictions": self._check_contradictions,
            "protocol_state": self._protocol_state,
            "tree": self._tree,
            "hardware_status": self._hardware_status,
        }
        return handlers.get(name)

    def _resolve_path(self, path: str) -> str:
        """Resolve a relative path against the repo root."""
        return os.path.normpath(os.path.join(self.repo_root, path))

    def _read_file(self, path: str) -> str:
        full = self._resolve_path(path)
        if not os.path.isfile(full):
            return f"Error: file not found: {path}"
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if len(content) > 12000:
                return f"(File is {len(content)} bytes — showing first 12000)\n{content[:12000]}"
            return content
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _read_file_range(self, path: str, offset: int = 0, limit: int = 500) -> str:
        full = self._resolve_path(path)
        if not os.path.isfile(full):
            return f"Error: file not found: {path}"
        limit = min(limit, 2000)
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            selected = lines[offset:offset + limit]
            result = "".join(
                f"{i + offset + 1:>6}: {l}"
                for i, l in enumerate(selected)
            )
            total = len(lines)
            end = offset + len(selected)
            return f"{path} lines {offset + 1}–{end} of {total}\n{result}"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def _write_file(self, path: str, content: str) -> str:
        full = self._resolve_path(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        try:
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            # Verify
            if os.path.isfile(full):
                actual = os.path.getsize(full)
                return f"OK: wrote {path} ({actual} bytes)"
            return f"Error: write reported success but file not found: {path}"
        except Exception as e:
            return f"Error writing {path}: {e}"

    def _edit_file(self, path: str, before: str, after: str) -> str:
        full = self._resolve_path(path)
        if not os.path.isfile(full):
            return f"Error: file not found: {path}"
        try:
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            count = content.count(before)
            if count == 0:
                return f"Error: pattern not found in {path}"
            if count > 1:
                return f"Error: pattern found {count} times in {path} — must be unique"
            new_content = content.replace(before, after, 1)
            with open(full, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"OK: edited {path} (1 replacement)"
        except Exception as e:
            return f"Error editing {path}: {e}"

    def _shell(self, command: str, timeout_secs: int = 30) -> str:
        try:
            argv = shlex.split(command)
            result = subprocess.run(
                argv,
                shell=False, capture_output=True, text=True,
                cwd=self.repo_root, timeout=timeout_secs,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\n--- stderr ---\n"
                output += result.stderr
            if result.returncode != 0:
                output = f"Exit code: {result.returncode}\n{output}"
            return output[:10000] if len(output) > 10000 else output
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {timeout_secs}s"
        except Exception as e:
            return f"Error: {e}"

    def _run_pytest(self, test_path: str = "bridge/tests/",
                    timeout: int = 120, extra_args: str = "") -> str:
        cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short", "--no-header"]
        if extra_args:
            cmd.extend(shlex.split(extra_args))
        try:
            result = subprocess.run(
                cmd, shell=False, capture_output=True, text=True,
                cwd=self.repo_root, timeout=timeout,
            )
            output = result.stdout or result.stderr
            # Summarize
            lines = output.splitlines()
            fail_lines = [l for l in lines if "FAILED" in l]
            pass_lines = [l for l in lines if "PASSED" in l]
            summary = [l for l in lines if "passed" in l or "failed" in l]
            summary_text = "\n".join(summary[:5]) if summary else ""
            fail_text = "\n".join(fail_lines[:10]) if fail_lines else ""
            pass_count = len([l for l in lines if "PASSED" in l])
            fail_count = len(fail_lines)

            msg = f"Exit: {result.returncode} | {pass_count} passed, {fail_count} failed"
            if summary_text:
                msg += f"\n{summary_text}"
            if fail_text:
                msg += f"\n\nFailures:\n{fail_text}"
            return msg
        except subprocess.TimeoutExpired:
            return f"Error: pytest timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    def _git_log(self, n: int = 10) -> str:
        return self._shell(f"git log --oneline -{n}", 10)

    def _git_diff(self, path: str = "") -> str:
        return self._shell(f"git diff {'-- ' + path if path else ''}", 10)

    def _git_status(self) -> str:
        return self._shell("git status --short", 10)

    def _git_commit(self, message: str) -> str:
        result = self._shell("git add -A", 10)
        return self._shell(f'git commit -m "{message}"', 10)

    def _bridge_health(self) -> str:
        h = self.bridge.health()
        return json.dumps(h, indent=2, default=str)

    def _bridge_get(self, path: str, timeout: int = 10) -> str:
        result = self.bridge.get(path, timeout)
        if result is None:
            return f"Error: bridge GET {path} failed"
        return json.dumps(result, indent=2, default=str)

    def _bridge_post(self, path: str, data: dict = None, timeout: int = 30) -> str:
        result = self.bridge.post(path, data or {}, timeout)
        if result is None:
            return f"Error: bridge POST {path} failed"
        return json.dumps(result, indent=2, default=str)

    def _methodology_query(self, keywords: str = "") -> str:
        entries = self._methodology_registry.query(keywords)
        return MethodologyRegistry.format_for_prompt(entries)

    def _methodology_add(self, failure_class: str, anti_pattern: str,
                         correct_pattern: str, agent_commit: str = "") -> str:
        self._methodology_registry.add(
            failure_class, anti_pattern, correct_pattern, agent_commit
        )
        return f"OK: added methodology entry [{failure_class}]"

    def _search_files(self, pattern: str, path: str = ".") -> str:
        full = self._resolve_path(path)
        if not os.path.isdir(full):
            return f"Error: directory not found: {path}"
        matches = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                if pattern in f or pattern in os.path.join(root, f):
                    rel = os.path.relpath(os.path.join(root, f), self.repo_root)
                    matches.append(rel)
        if not matches:
            return f"No files matching '{pattern}'"
        return "\n".join(matches[:100])

    def _grep(self, pattern: str, path: str = ".", include: str = "*.py") -> str:
        full = self._resolve_path(path)
        if not os.path.isdir(full):
            return f"Error: directory not found: {path}"
        matches = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "node_modules"]
            for f in files:
                if not f.endswith(include.replace("*", "")) if "*" in include else True:
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        for i, line in enumerate(fh, 1):
                            if pattern in line:
                                rel = os.path.relpath(fpath, self.repo_root)
                                matches.append(f"{rel}:{i}: {line.rstrip()[:200]}")
                except Exception:
                    continue
        if not matches:
            return f"No matches for '{pattern}'"
        return "\n".join(matches[:100])

    def _check_invariants(self, focus: str = "") -> str:
        """Check PV-CI invariants. Attempts to import and run the self-test."""
        if _HAS_GOVERNANCE:
            try:
                from _daemon_tools_schema import governance_self_test
                result = governance_self_test()
                return json.dumps(result, indent=2, default=str)
            except Exception as e:
                return f"Error running invariant check: {e}"
        return "Invariant check not available (governance module not imported)"

    def _check_contradictions(self) -> str:
        """Check FSCA contradictions from the bridge."""
        contradictions = self.bridge.get_contradictions()
        if not contradictions:
            return "No contradictions detected (bridge may be unreachable)"
        return json.dumps(contradictions, indent=2, default=str)

    def _protocol_state(self) -> str:
        state = self.bridge.get_protocol_state()
        return json.dumps(state, indent=2, default=str)

    def _tree(self, path: str = ".", depth: int = 2) -> str:
        full = self._resolve_path(path)
        if not os.path.isdir(full):
            return f"Error: directory not found: {path}"
        result = []
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "node_modules"]
            rel = os.path.relpath(root, self.repo_root)
            level = rel.count(os.sep) if rel != "." else 0
            if level > depth:
                dirs.clear()
                continue
            indent = "  " * level
            result.append(f"{indent}{os.path.basename(root) or '.'}/")
            subindent = "  " * (level + 1)
            for f in files:
                if f.endswith(".pyc"):
                    continue
                fpath = os.path.join(root, f)
                try:
                    size = os.path.getsize(fpath)
                    result.append(f"{subindent}{f} ({size:,} bytes)")
                except Exception:
                    result.append(f"{subindent}{f}")
        return "\n".join(result[:200])

    def _hardware_status(self) -> str:
        """Stub — returns a placeholder. Real hardware detection is in the watcher."""
        return (
            "Hardware status depends on the Hardware Watcher thread.\n"
            "Run the tool in TUI mode to see live hardware state.\n"
            "Or check: hardware_watcher.last_state"
        )

    methodology_registry: MethodologyRegistry = None


