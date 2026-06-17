#!/usr/bin/env python3
"""
QorTroller CLI AI Agent — Dumb Rendering Client (Hive Mind)
=============================================================

A Rich-based terminal chat client for the QorTroller (VAPI) protocol.
This is a "dumb" rendering frontend in the Hive Mind architecture.

It connects to the QorTroller Daemon (qortroller_daemon.py) for ALL
AI processing:
  • POST /chat    — Sends user messages to the central brain
  • GET  /history — Pulls unified conversation history
  • GET  /status  — Checks brain status
  • GET  /health  — Daemon health check

The daemon owns the LLM connection, the system prompt, the autonomous
tool execution loop, and the shared SQLite memory (agent_memory.db).

Usage:
  python qortroller_cli_agent.py

Requirements:
  pip install rich requests
  qortroller_daemon.py must be running on localhost:8080
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
#  Ensure we can import from bridge/ for reusable helpers (if needed)
# ═══════════════════════════════════════════════════════════════════════════════

_root_dir = Path(__file__).parent.resolve()
_bridge_dir = str(_root_dir / "bridge")
if _bridge_dir not in sys.path:
    sys.path.insert(0, _bridge_dir)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

# ═══════════════════════════════════════════════════════════════════════════════
#  Rich imports (UI rendering only — no AI logic)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from rich.console import Console
    from rich.markdown import Markdown as RichMarkdown
    from rich.panel import Panel
    from rich.table import Table
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.style import Style
    from rich.align import Align
    from rich.columns import Columns
    from rich.box import ROUNDED
    from rich.layout import Layout
    from rich.live import Live
    from rich.prompt import Prompt
    from rich.rule import Rule
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════════════════
#  Constants & Brand
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "QorTroller CLI Agent"
APP_VERSION = "2.0.0"
CLIENT_TYPE = "hive-mind-client"

C_GREEN = "#22c55e"
C_GREEN_DIM = "#166534"
C_CYAN = "#4a9eff"
C_YELLOW = "#eab308"
C_RED = "#ef4444"
C_BRIGHT = "#f0fdf4"
C_MUTED = "#6b7280"

DAEMON_URL = os.environ.get("QORTROLLER_DAEMON_URL", "http://localhost:8080")
DAEMON_CHAT_URL = f"{DAEMON_URL}/chat"
DAEMON_HISTORY_URL = f"{DAEMON_URL}/history"
DAEMON_STATUS_URL = f"{DAEMON_URL}/status"
DAEMON_HEALTH_URL = f"{DAEMON_URL}/health"

# ═══════════════════════════════════════════════════════════════════════════════
#  Daemon Client — All communication with the central brain
# ═══════════════════════════════════════════════════════════════════════════════


class DaemonClient:
    """HTTP client for the QorTroller Daemon Hive Mind brain.

    All AI processing happens on the daemon. This client just sends
    and receives JSON.
    """

    def __init__(self, base_url: str = DAEMON_URL):
        self.base_url = base_url.rstrip("/")
        self._cached_history: list[dict] = []

    # ── Basic helpers ────────────────────────────────────────────────────

    def _get(self, path: str, timeout: float = 5.0) -> Optional[dict]:
        """Sync GET to daemon."""
        import requests
        try:
            r = requests.get(
                f"{self.base_url}{path}",
                timeout=timeout,
                proxies={"http": None, "https": None},
            )
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    def _post(self, path: str, payload: dict, timeout: float = 30.0) -> Optional[dict]:
        """Sync POST to daemon."""
        import requests
        try:
            r = requests.post(
                f"{self.base_url}{path}",
                json=payload,
                timeout=timeout,
                proxies={"http": None, "https": None},
            )
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    # ── Health check ─────────────────────────────────────────────────────

    def health(self) -> Optional[dict]:
        """GET /health — check daemon is alive."""
        return self._get("/health")

    def is_alive(self) -> bool:
        """Quick check if daemon is running."""
        health = self.health()
        return health is not None and health.get("status") == "ok"

    # ── Chat ─────────────────────────────────────────────────────────────

    def send_message(self, text: str, timeout: float = 120.0) -> Optional[dict]:
        """POST /chat — send message to the central brain.

        The daemon runs the full autonomous tool loop and returns
        the final response. This may take a while for multi-tool queries.
        """
        return self._post("/chat", {"message": text}, timeout=timeout)

    # ── History ──────────────────────────────────────────────────────────

    def get_history(self, since_id: int = 0) -> list[dict]:
        """GET /history — fetch unified conversation history."""
        path = f"/history?since_id={since_id}" if since_id > 0 else "/history"
        data = self._get(path)
        if data:
            msgs = data.get("messages", [])
            self._cached_history = msgs
            return msgs
        return []

    def get_all_history(self) -> list[dict]:
        """Fetch ALL history."""
        data = self._get("/history?limit=500")
        if data:
            msgs = data.get("messages", [])
            self._cached_history = msgs
            return msgs
        return []

    # ── Status ───────────────────────────────────────────────────────────

    def get_status(self) -> Optional[dict]:
        """GET /status — brain status."""
        return self._get("/status")

    @property
    def brain_status(self) -> str:
        """Quick status string."""
        s = self.get_status()
        if s:
            return s.get("brain_status", "unknown")
        return "offline"


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI Agent — Pure Rendering Client
# ═══════════════════════════════════════════════════════════════════════════════


class QorTrollerCLIAgent:
    """Standalone Rich-based CLI chat client for the Hive Mind Daemon.

    This is a PURE RENDERING CLIENT. It contains NO AI logic, NO system
    prompt, NO tool execution, and NO LLM connection. It delegates ALL
    cognitive work to the QorTroller Daemon.
    """

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.daemon = DaemonClient()
        self._response_in_progress = False
        self._last_seen_id = 0  # Tracked by background poller

    # ── Init ─────────────────────────────────────────────────────────────

    def check_daemon(self) -> bool:
        """Check if the daemon is running."""
        if self.daemon.is_alive():
            return True
        self.console.print(
            f"  [red]![/] Daemon not reachable at {DAEMON_URL}"
        )
        self.console.print(
            "  [dim]Start it with: python qortroller_daemon.py[/dim]"
        )
        return False

    def print_header(self):
        """Print the branded header."""
        header = Text()
        header.append("╔" + "═" * 58 + "╗\n", style=C_GREEN)
        header.append("║", style=C_GREEN)
        header.append(f"  {APP_NAME}  ", style=Style(bold=True, color=C_GREEN))
        header.append(f"v{APP_VERSION}", style=C_MUTED)
        header.append(" " * (18 - len(APP_VERSION)))
        header.append(f"[{CLIENT_TYPE}]", style=C_MUTED)
        header.append(" " * 8)
        header.append("║\n", style=C_GREEN)
        header.append("║", style=C_GREEN)
        header.append(
            "  QorTroller VAPI Protocol — Hive Mind Client     ",
            style=C_MUTED,
        )
        header.append("║\n", style=C_GREEN)
        header.append("╚" + "═" * 58 + "╝", style=C_GREEN)
        self.console.print(header)
        self.console.print()

    def print_welcome(self):
        """Print welcome message with daemon status."""
        health = self.daemon.health()
        if health:
            self.console.print(
                Panel(
                    "[green]QorTroller Daemon connected[/] "
                    f"(model: {health.get('llm_model', '?')}, "
                    f"brain: {health.get('brain', 'idle')}, "
                    f"messages: {health.get('message_count', 0)})",
                    border_style=C_GREEN_DIM,
                    box=ROUNDED,
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[red]Daemon offline at {DAEMON_URL}[/]\n"
                    "Start with: [green]python qortroller_daemon.py[/]",
                    border_style=C_RED,
                    box=ROUNDED,
                )
            )

        self.console.print()
        self.console.print(
            "  [dim]Type your message or use /commands. Press [/dim]"
            "[green]/help[/][dim] for available commands.[/dim]"
        )
        self.console.print(Rule(style=C_GREEN_DIM))
        self.console.print()

    # ── Message Display ──────────────────────────────────────────────────

    def display_user_message(self, content: str):
        """Display a user message in a styled panel."""
        panel = Panel(
            Text(content, style=C_BRIGHT),
            title="[cyan]You[/]",
            border_style=C_CYAN,
            box=ROUNDED,
            padding=(0, 1),
        )
        self.console.print(panel)
        self.console.print()

    def display_ai_message(self, content: str):
        """Display an AI response with Markdown rendering."""
        try:
            md = RichMarkdown(content)
            panel = Panel(
                md,
                title="[green]QorTroller AI (Daemon)[/]",
                border_style=C_GREEN,
                box=ROUNDED,
                padding=(0, 1),
            )
        except Exception:
            panel = Panel(
                Text(content, style=C_BRIGHT),
                title="[green]QorTroller AI (Daemon)[/]",
                border_style=C_GREEN,
                box=ROUNDED,
                padding=(0, 1),
            )
        self.console.print(panel)
        self.console.print()

    def display_system_message(self, content: str):
        """Display a system/side message in muted style."""
        self.console.print(f"  [dim]{content}[/dim]")
        self.console.print()

    def display_error_message(self, content: str):
        """Display an error message."""
        self.console.print(f"  [red]![/] {content}")

    def display_brain_status(self, status: str):
        """Show current brain status."""
        if status == "thinking":
            self.console.print("  [dim]Brain: thinking...[/dim]")
        elif status == "idle":
            pass  # Don't spam "idle"
        elif status.startswith("running tool"):
            self.console.print(f"  [yellow]Brain:[/] {status}")
        else:
            self.console.print(f"  [dim]Brain: {status}[/dim]")

    # ── Display History ──────────────────────────────────────────────────

    def display_history(self, messages: list[dict]):
        """Display a list of messages from history."""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user":
                self.display_user_message(content)
            elif role == "assistant":
                self.display_ai_message(content)
            elif role == "system":
                # Skip system prompt — it's metadata
                pass

    # ── Chat with Daemon ─────────────────────────────────────────────────

    def send_to_daemon(self, user_text: str):
        """Send user message to the daemon and display the response.

        This is the CORE interaction: dumb client sends to daemon,
        daemon brain processes it fully, returns the final response.
        """
        if self._response_in_progress:
            self.console.print("[yellow]![/] A response is already in progress...")
            return

        self.display_user_message(user_text)
        self._response_in_progress = True

        try:
            # Show thinking indicator
            self.console.print("  [dim]Sending to daemon brain...[/dim]")

            # Send to daemon — this blocks until the FULL autonomous
            # tool loop completes on the daemon side
            result = self.daemon.send_message(user_text, timeout=120.0)

            # Clear the "sending" line
            self.console.print("\033[1A\033[K", end="")

            if result is None:
                self.display_error_message(
                    f"Daemon did not respond. Check that qortroller_daemon.py "
                    f"is running on {DAEMON_URL}."
                )
                return

            response = result.get("response", "")
            msg_type = result.get("type", "unknown")
            tool_iters = result.get("tool_iterations", 0)

            if not response:
                self.display_error_message("Daemon returned an empty response.")
                return

            # Display the AI's response
            self.display_ai_message(response)

            # Track message_id so background poller doesn't re-show it
            msg_id = result.get("message_id", 0)
            if msg_id > self._last_seen_id:
                self._last_seen_id = msg_id

            # Show metadata if tools were used
            if tool_iters and tool_iters > 1:
                self.display_system_message(
                    f"(Used {tool_iters - 1} tool iteration(s) to compose response)"
                )

        except Exception as e:
            self.console.print("\033[1A\033[K", end="")
            self.display_error_message(f"Error communicating with daemon: {e}")
        finally:
            self._response_in_progress = False

    # ── Slash Commands ───────────────────────────────────────────────────

    async def handle_command(self, cmd: str) -> bool:
        """Handle a slash command. Returns True if handled."""
        parts = cmd.lower().split()
        command = parts[0] if parts else "/help"

        if command == "/help":
            self._cmd_help()
            return True
        elif command == "/clear":
            self._cmd_clear()
            return True
        elif command == "/export":
            self._cmd_export()
            return True
        elif command == "/daemon":
            self._cmd_daemon_status()
            return True
        elif command == "/history":
            self._cmd_show_history()
            return True
        else:
            # All other commands (/status, /agents, /phase, /separation,
            # /read, /ls, /git, /context, /tools, etc.) are forwarded
            # to the daemon as chat messages for the AI brain to handle.
            self.console.print(
                f"  [dim]Forwarding '{cmd}' to daemon brain...[/dim]"
            )
            self.send_to_daemon(cmd)
            return True

    def _cmd_help(self):
        """Show help."""
        self.console.print(
            Panel(
                Text(
                    "QorTroller CLI Agent (Hive Mind Client)\n"
                    "════════════════════════════════════════\n\n"
                    "This is a DUMB RENDERING CLIENT — all AI processing\n"
                    "happens on the QorTroller Daemon.\n\n"
                    "Slash Commands:\n"
                    "  /help              Show this help\n"
                    "  /clear             Clear the screen\n"
                    "  /export            Export conversation to file\n"
                    "  /daemon            Show daemon status\n"
                    "  /history           Show recent message history\n\n"
                    "Multi-line / Long Task Input:\n"
                    "  /task              Enter block input mode — type your\n"
                    "  <<<                full task across multiple lines, then\n"
                    "                     type  >>>  alone to send as ONE message.\n"
                    "  /task <text>       Seed with first line, continue in block mode.\n"
                    "  Use this for engineering tasks to avoid the CLI\n"
                    "  splitting pasted text into separate messages.\n\n"
                    "All other commands (/status, /read, /ls, /git,\n"
                    "/agents, /phase, /separation, /context, /tools)\n"
                    "are forwarded to the daemon AI brain.\n\n"
                    "Navigation:\n"
                    "  Type your message and press Enter.\n"
                    "  Press Ctrl+C to exit.",
                    style=C_BRIGHT,
                ),
                title="[green]QorTroller CLI — Commands[/]",
                border_style=C_GREEN,
                box=ROUNDED,
            )
        )

    def _cmd_clear(self):
        """Clear the screen."""
        self.console.clear()

    def _cmd_daemon_status(self):
        """Show daemon status."""
        status = self.daemon.get_status()
        health = self.daemon.health()

        if not status and not health:
            self.display_error_message(
                f"Daemon offline at {DAEMON_URL}.\n"
                "Start with: python qortroller_daemon.py"
            )
            return

        table = Table(
            title="Daemon Status",
            border_style=C_GREEN,
            box=ROUNDED,
        )
        table.add_column("Field", style=C_CYAN)
        table.add_column("Value", style=C_BRIGHT)

        if health:
            table.add_row("Status", health.get("status", "?"))
            table.add_row("Mode", health.get("mode", "?"))
            table.add_row("LLM Model", health.get("llm_model", "?"))
            table.add_row("LLM Key", "✓" if health.get("llm_configured") else "✗")
            table.add_row("Brain", health.get("brain", "?"))
            table.add_row("Messages", str(health.get("message_count", 0)))

        if status:
            table.add_row("Version", status.get("app_version", "?"))
            table.add_row("Message Count", str(status.get("message_count", 0)))
            table.add_row("Brain Status", status.get("brain_status", "?"))

        self.console.print(table)
        self.console.print()

    def _cmd_export(self):
        """Export conversation to file."""
        try:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = _root_dir / "tui_exports" / f"qortroller_chat_{ts}.json"
            export_path.parent.mkdir(exist_ok=True)

            messages = self.daemon.get_all_history()
            export_data = {
                "app": APP_NAME,
                "version": APP_VERSION,
                "client_type": CLIENT_TYPE,
                "exported_at": datetime.datetime.now().isoformat(),
                "daemon_url": DAEMON_URL,
                "messages": messages,
            }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)

            self.console.print(
                f"  [green]✓[/] Conversation exported to {export_path}"
            )
        except Exception as e:
            self.display_error_message(f"Export failed: {e}")

    def _cmd_show_history(self):
        """Show recent message history from the daemon."""
        messages = self.daemon.get_all_history()
        if not messages:
            self.display_system_message("No messages in history yet.")
            return

        self.console.print(
            Panel(
                f"[dim]Showing {len(messages)} messages from shared daemon memory[/dim]",
                border_style=C_GREEN_DIM,
                box=ROUNDED,
            )
        )
        self.display_history(messages)

    # ── Main Chat Loop ───────────────────────────────────────────────────

    async def _background_poller(self):
        """Background task: continuously poll /history and /status.

        Polls /history every 3s to catch messages from other clients,
        and /status every 5s to update brain state display.
        Uses _last_seen_id to avoid showing duplicate messages.
        """
        history_interval = 3.0
        status_interval = 5.0
        last_history_poll = 0.0
        last_status_poll = 0.0

        try:
            while True:
                now = time.monotonic()

                # Poll /history every 3s
                if now - last_history_poll >= history_interval:
                    last_history_poll = now
                    try:
                        new_msgs = self.daemon.get_history(
                            since_id=self._last_seen_id
                        )
                        if new_msgs:
                            # Update last_seen_id to the most recent
                            self._last_seen_id = max(
                                self._last_seen_id,
                                max(m.get("id", 0) for m in new_msgs),
                            )
                            # Display new messages silently
                            for m in new_msgs:
                                role = m.get("role", "")
                                content = m.get("content", "")
                                if not content:
                                    continue
                                if role == "user":
                                    # Only show other clients' messages
                                    # (ours are displayed by send_to_daemon)
                                    pass
                                elif role == "assistant":
                                    self.display_ai_message(content)
                    except Exception:
                        pass

                # Poll /status every 5s
                if now - last_status_poll >= status_interval:
                    last_status_poll = now
                    try:
                        status = self.daemon.get_status()
                        if status:
                            brain = status.get("brain_status", "")
                            if brain != "idle":
                                self.display_brain_status(brain)
                    except Exception:
                        pass

                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass

    async def run_async(self):
        """Async main loop with continuous background polling."""
        self._last_seen_id = 0
        self.print_header()

        if not self.check_daemon():
            self.console.print()
            self.console.print(
                "  [dim]The daemon is required for all AI operations.\n"
                "  Start it in another terminal with:[/dim]"
            )
            self.console.print(
                "  [green]  python qortroller_daemon.py[/green]"
            )
            return

        self.print_welcome()

        # Show recent history on connect
        history = self.daemon.get_all_history()
        if history:
            if history:
                self._last_seen_id = max(m.get("id", 0) for m in history)
            self.display_system_message(
                f"Loaded {len(history)} messages from shared memory."
            )
            self.display_history(history[-5:])

        # Start background poller
        poller_task = asyncio.create_task(self._background_poller())

        # Main chat loop
        try:
            while True:
                try:
                    user_input = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: Prompt.ask("[cyan]>[/]").strip(),
                    )
                except (EOFError, KeyboardInterrupt):
                    self.console.print()
                    break

                if not user_input:
                    continue

                # ── Block input mode (/task or <<< trigger) ──────────────
                # Typing  /task  or  <<<  enters multi-line mode.
                # All subsequent lines are collected until a line containing
                # only  >>>  (or an empty line after /task) is entered.
                # The full block is sent as ONE message — no splits.
                if user_input in ("/task", "<<<") or user_input.startswith("/task "):
                    # If /task already has content after it, use that as first line
                    seed = user_input[6:].strip() if user_input.startswith("/task ") else ""
                    lines = [seed] if seed else []
                    self.console.print(
                        "  [dim]Multi-line mode — type your full task, "
                        "then enter [/dim][green]>>>[/][dim] on its own line to send.[/dim]"
                    )
                    while True:
                        try:
                            line = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: input("  … ")
                            )
                        except (EOFError, KeyboardInterrupt):
                            break
                        if line.strip() == ">>>":
                            break
                        lines.append(line)
                    user_input = " ".join(lines).strip()
                    if not user_input:
                        self.console.print("  [dim](empty task — cancelled)[/dim]")
                        continue
                    self.console.print()

                # Check for slash commands
                if user_input.startswith("/"):
                    handled = await self.handle_command(user_input)
                    if not handled:
                        self.display_error_message(
                            f"Unknown command: {user_input}\n"
                            "  Type /help for available commands."
                        )
                else:
                    self.send_to_daemon(user_input)

        except KeyboardInterrupt:
            self.console.print()
        finally:
            poller_task.cancel()
            self.console.print(Rule(style=C_GREEN_DIM))
            self.console.print("[green]Goodbye![/]")

    def run(self):
        """Run the CLI agent (sync entry point)."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            self.console.print()
            self.console.print("[green]Goodbye![/]")


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry Points
# ═══════════════════════════════════════════════════════════════════════════════


def main():
    """Main entry point."""
    if not RICH_AVAILABLE:
        print("Rich library not installed. Install with: pip install rich")
        sys.exit(1)

    agent = QorTrollerCLIAgent()
    agent.run()


if __name__ == "__main__":
    import asyncio
    main()