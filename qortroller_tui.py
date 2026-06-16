#!/usr/bin/env python3
"""
QorTroller TUI AI Agent — Dumb Rendering Client (Hive Mind)
=============================================================

A Textual-based Terminal User Interface for the QorTroller (VAPI) protocol.
This is a "dumb" rendering frontend in the Hive Mind architecture.

It connects to the QorTroller Daemon (qortroller_daemon.py) for ALL
AI processing:
  • POST /chat    — Sends user messages to the central brain
  • GET  /history — Pulls unified conversation history
  • GET  /health  — Daemon health check

The daemon owns the LLM connection, the system prompt, the autonomous
tool execution loop, and the shared SQLite memory (agent_memory.db).

Usage:
  python qortroller_tui.py

Requirements:
  pip install textual rich aiohttp requests
  qortroller_daemon.py must be running on localhost:8080
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure we can import from bridge/ for reusable helpers
_root_dir = Path(__file__).parent.resolve()
_bridge_dir = str(_root_dir / "bridge")
if _bridge_dir not in sys.path:
    sys.path.insert(0, _bridge_dir)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

# ── Textual imports ──────────────────────────────────────────────────────────
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive, var
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Button, Header, Footer, Input, Label, ListView, ListItem,
    RichLog, Static, TextArea, Markdown, ContentSwitcher,
    TabbedContent, TabPane, LoadingIndicator, Rule, Checkbox,
)
from textual.widgets._markdown import Markdown as MarkdownWidget

# ── Rich imports ─────────────────────────────────────────────────────────────
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.markdown import Markdown as RichMarkdown
from rich.console import Console, RenderableType
from rich.syntax import Syntax
from rich.align import Align
from rich.box import MINIMAL, ROUNDED, DOUBLE, HEAVY
from rich.style import Style
from rich.columns import Columns

# ═══════════════════════════════════════════════════════════════════════════════
#  Constants & Brand
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "QorTroller TUI AI Agent"
APP_VERSION = "2.0.0"
CLIENT_TYPE = "hive-mind-client"

BRAND_COLOR = "#22c55e"
BRAND_COLOR_DIM = "#166534"
ACCENT_COLOR = "#4a9eff"
BGDARK = "#020408"
SURFACE = "#0a0e14"
BORDER_COLOR = "#1a2a3a"
TEXT_MUTED = "#6b7280"
TEXT_BRIGHT = "#f0fdf4"

TIMESTAMP_FMT = "%H:%M:%S"

DAEMON_URL = os.environ.get("QORTROLLER_DAEMON_URL", "http://localhost:8080")
BRIDGE_BASE_URL = os.environ.get("VAPI_BRIDGE_URL", "http://localhost:8000")

# ═══════════════════════════════════════════════════════════════════════════════
#  Daemon Client — All communication with the central brain
# ═══════════════════════════════════════════════════════════════════════════════


async def _daemon_get(path: str, timeout: float = 5.0) -> Optional[dict]:
    """Async HTTP GET to the daemon."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{DAEMON_URL}{path}",
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except ImportError:
        return await _daemon_get_sync(path, timeout)
    except Exception:
        return None


async def _daemon_get_sync(path: str, timeout: float) -> Optional[dict]:
    """Sync fallback via executor."""
    import requests
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: requests.get(
                f"{DAEMON_URL}{path}",
                timeout=timeout,
                proxies={"http": None, "https": None},
            ),
        )
        return result.json() if result.status_code == 200 else None
    except Exception:
        return None


async def _daemon_post(path: str, payload: dict, timeout: float = 30.0) -> Optional[dict]:
    """Async HTTP POST to the daemon."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{DAEMON_URL}{path}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except ImportError:
        return await _daemon_post_sync(path, payload, timeout)
    except Exception:
        return None


async def _daemon_post_sync(path: str, payload: dict, timeout: float) -> Optional[dict]:
    """Sync fallback via executor."""
    import requests
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: requests.post(
                f"{DAEMON_URL}{path}",
                json=payload,
                timeout=timeout,
                proxies={"http": None, "https": None},
            ),
        )
        return result.json() if result.status_code == 200 else None
    except Exception:
        return None


# Shortcuts for frequent calls
async def daemon_health() -> Optional[dict]:
    """Check daemon health."""
    return await _daemon_get("/health", timeout=2.0)


async def daemon_send_message(text: str, timeout: float = 120.0) -> Optional[dict]:
    """POST /chat — send message to central brain."""
    return await _daemon_post("/chat", {"message": text}, timeout=timeout)


async def daemon_get_history(since_id: int = 0) -> list[dict]:
    """GET /history — get unified conversation history."""
    path = f"/history?since_id={since_id}" if since_id > 0 else "/history"
    data = await _daemon_get(path)
    if data:
        return data.get("messages", [])
    return []


async def daemon_get_all_history() -> list[dict]:
    """GET /history?limit=500 — all history."""
    data = await _daemon_get("/history?limit=500")
    if data:
        return data.get("messages", [])
    return []


async def daemon_get_status() -> Optional[dict]:
    """GET /status — brain status."""
    return await _daemon_get("/status")


# ═══════════════════════════════════════════════════════════════════════════════
#  Custom Widgets
# ═══════════════════════════════════════════════════════════════════════════════


class StatusIndicator(Static):
    """A small dot + label status indicator."""

    def __init__(self, label: str, initial: str = "unknown", **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._status = initial

    def set_status(self, status: str):
        self._status = status
        self.refresh()

    def on_mount(self):
        self.set_status(self._status)

    def render(self) -> RenderableType:
        color_map = {
            "ok": BRAND_COLOR,
            "connected": BRAND_COLOR,
            "healthy": BRAND_COLOR,
            "pass": BRAND_COLOR,
            "active": ACCENT_COLOR,
            "warning": "#eab308",
            "error": "#ef4444",
            "disconnected": "#ef4444",
            "unknown": TEXT_MUTED,
            "inactive": TEXT_MUTED,
        }
        dot_color = color_map.get(self._status, TEXT_MUTED)
        return Text.assemble(
            ("● ", dot_color),
            (self._label, Style(color=TEXT_MUTED)),
            " ",
            (self._status.replace("_", " ").title(), Style(color=TEXT_BRIGHT, bold=True)),
        )


class StatusPanel(Vertical):
    """Protocol status sidebar panel."""

    def compose(self) -> ComposeResult:
        yield Static("╔═══ HIVE MIND ═══╗", classes="panel-header")
        yield StatusIndicator("Daemon", "disconnected", id="status-daemon")
        yield StatusIndicator("LLM", "unknown", id="status-llm")
        yield StatusIndicator("Brain", "unknown", id="status-brain")
        yield StatusIndicator("Messages", "0", id="status-messages")
        yield Rule(line_style="dashed", classes="status-rule")
        yield Static("╔═══ BRIDGE ═══╗", classes="panel-header")
        yield StatusIndicator("Bridge", "disconnected", id="status-bridge")
        yield StatusIndicator("Phase", "unknown", id="status-phase")
        yield StatusIndicator("Agents", "unknown", id="status-agents")
        yield StatusIndicator("Separation", "unknown", id="status-separation")
        yield StatusIndicator("All Pairs", "unknown", id="status-all-pairs")
        yield StatusIndicator("Tournament", "unknown", id="status-tournament")
        yield Rule(line_style="dashed", classes="status-rule")
        yield Static("╔═══ CMDS ═══╗", classes="panel-header")
        yield Static("  /daemon   — Daemon status", classes="cmd-hint")
        yield Static("  /history  — Show history", classes="cmd-hint")
        yield Static("  /help     — All commands", classes="cmd-hint")
        yield Static("  /export   — Save chat", classes="cmd-hint")
        yield Static("  /clear    — Clear chat", classes="cmd-hint")
        yield Rule(line_style="dashed", classes="status-rule")
        yield Static("All /status, /agents, /read, /ls, /git,", classes="cmd-hint")
        yield Static("/phase, /separation commands are", classes="cmd-hint")
        yield Static("forwarded to the daemon brain.", classes="cmd-hint")


class ChatLog(RichLog):
    """Scrollable chat history that renders Markdown for AI responses."""

    def add_user_message(self, content: str):
        ts = datetime.datetime.now().strftime(TIMESTAMP_FMT)
        header = Text.assemble(
            (f"\n  [{ts}] ", Style(color=TEXT_MUTED, dim=True)),
            ("YOU", Style(color=ACCENT_COLOR, bold=True)),
        )
        self.write(header)
        self.write(Text(f"  {content}", style=Style(color=TEXT_BRIGHT)))
        self.write(Text(""))

    def add_ai_message(self, content: str):
        ts = datetime.datetime.now().strftime(TIMESTAMP_FMT)
        header = Text.assemble(
            (f"\n  [{ts}] ", Style(color=TEXT_MUTED, dim=True)),
            ("QorTroller AI (Daemon)", Style(color=BRAND_COLOR, bold=True)),
        )
        self.write(header)
        try:
            md = RichMarkdown(content, style="dim")
            self.write(md)
        except Exception:
            self.write(Text(f"  {content}", style=Style(color=TEXT_BRIGHT)))
        self.write(Text(""))

    def add_system_message(self, content: str, style: str = "italic"):
        self.write(Text(f"  {content}", style=Style(color=TEXT_MUTED, italic=True)))

    def add_error_message(self, content: str):
        self.write(Text(f"  ✗ {content}", style=Style(color="#ef4444", bold=True)))

    def add_brain_status(self, status: str):
        """Show current brain status."""
        if status == "thinking":
            self.write(Text("  ⟳ Brain: thinking...", style=Style(color=TEXT_MUTED, italic=True)))
        elif status.startswith("running tool"):
            self.write(Text(f"  ⟳ Brain: {status}", style=Style(color="#eab308", italic=True)))


# ═══════════════════════════════════════════════════════════════════════════════
#  Modal Screens
# ═══════════════════════════════════════════════════════════════════════════════


class HelpScreen(ModalScreen):
    """Help overlay."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("╔════════════════════════════════════╗", classes="help-title"),
            Static("║   QorTroller TUI — Hive Mind      ║", classes="help-title"),
            Static("╚════════════════════════════════════╝", classes="help-title"),
            Rule(),
            Static("Hive Mind Architecture:", classes="help-section"),
            Static("  This client is a DUMB RENDERING FRONTEND."),
            Static("  All AI processing happens on the daemon."),
            Static("  Both CLI and TUI share one brain + memory."),
            Static(""),
            Static("Slash Commands (handled locally):", classes="help-section"),
            Static("  /help      — Show this help screen"),
            Static("  /clear     — Clear chat display"),
            Static("  /export    — Export conversation to file"),
            Static("  /daemon    — Show daemon status"),
            Static("  /history   — Show shared chat history"),
            Static(""),
            Static("Slash Commands (forwarded to daemon brain):", classes="help-section"),
            Static("  /status, /agents, /phase, /separation,"),
            Static("  /read <path>, /ls, /git, /context,"),
            Static("  /tools, /tournament, /bbg, /maturity"),
            Rule(),
            Static("Keyboard Shortcuts:", classes="help-section"),
            Static("  Ctrl+Q       — Quit"),
            Static("  Ctrl+L       — Clear chat"),
            Static("  Ctrl+S       — Export chat"),
            Static("  Tab          — Focus cycle"),
            Static("  Up/Down      — Scroll"),
            Rule(),
            Static("  Press any key to close", classes="help-footer"),
            id="help-dialog",
        )

    def on_key(self, event):
        self.dismiss()


class ConfirmScreen(ModalScreen):
    """Confirmation dialog."""

    def __init__(self, message: str, confirm_text: str = "Confirm", **kwargs):
        super().__init__(**kwargs)
        self._message = message
        self._confirm_text = confirm_text

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self._message, id="confirm-message"),
            Horizontal(
                Button("Cancel", variant="default", id="cancel-btn"),
                Button(self._confirm_text, variant="primary", id="confirm-btn"),
                id="confirm-buttons",
            ),
            id="confirm-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm-btn":
            self.dismiss(True)
        else:
            self.dismiss(False)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main TUI Application
# ═══════════════════════════════════════════════════════════════════════════════

class QorTrollerTUI(App):
    """The QorTroller Terminal AI Agent — Hive Mind rendering client."""

    TITLE = APP_NAME
    SUB_TITLE = f"v{APP_VERSION} — Hive Mind Client"

    CSS = """
    Screen {
        background: #020408;
    }

    .app-root {
        height: 100%;
        width: 100%;
    }

    .chat-container {
        height: 100%;
        width: 100%;
        background: #020408;
        border: none;
    }

    .main-layout {
        height: 100%;
        width: 100%;
    }

    .chat-column {
        height: 100%;
        width: 1fr;
        min-width: 40;
        background: #020408;
    }

    .sidebar-column {
        height: 100%;
        width: 32;
        min-width: 28;
        background: #0a0e14;
        border-left: solid #1a2a3a;
        padding: 0 1;
    }

    StatusPanel {
        height: 100%;
        width: 100%;
    }

    StatusPanel > Static {
        margin: 0;
    }

    StatusPanel > Rule {
        margin: 1 0;
        color: #1a2a3a;
    }

    .panel-header {
        color: #22c55e;
        text-style: bold;
        padding: 1 0 0 0;
    }

    .cmd-hint {
        color: #6b7280;
        padding: 0 0 0 0;
    }

    .status-rule {
        margin: 1 0;
    }

    .chat-history {
        height: 1fr;
        width: 100%;
        border: none;
        background: #020408;
        padding: 0 0 0 1;
        margin: 0;
    }

    .input-container {
        height: 3;
        width: 100%;
        background: #0a0e14;
        border-top: solid #1a2a3a;
        padding: 0 1;
    }

    .input-container Input {
        width: 100%;
        background: #0a0e14;
        color: #f0fdf4;
        border: none;
        padding: 0 0 0 1;
    }

    .input-container Input:focus {
        border: none;
    }

    .input-container .input-prompt {
        color: #22c55e;
        text-style: bold;
        width: 2;
    }

    /* Help dialog */
    #help-dialog {
        width: 62;
        height: auto;
        min-height: 14;
        padding: 1 2;
        background: #0a0e14;
        border: solid #22c55e;
        margin: 2 2;
    }

    .help-title {
        color: #22c55e;
        text-style: bold;
        text-align: center;
    }

    .help-section {
        color: #4a9eff;
        text-style: bold;
        margin: 1 0 0 0;
    }

    .help-footer {
        color: #6b7280;
        text-align: center;
        margin: 1 0 0 0;
    }

    /* Confirm dialog */
    #confirm-dialog {
        width: 50;
        height: auto;
        min-height: 8;
        padding: 1 2;
        background: #0a0e14;
        border: solid #4a9eff;
        margin: 4 2;
    }

    #confirm-message {
        color: #f0fdf4;
        text-align: center;
        margin: 1 0;
    }

    #confirm-buttons {
        align: center middle;
        margin: 1 0;
    }

    #confirm-buttons Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("ctrl+s", "export_chat", "Export", show=True),
        Binding("slash", "focus_input", "Input"),
        Binding("escape", "focus_input", "Focus Input"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._response_in_progress = False
        self._conversation_file: Optional[Path] = None
        self._last_seen_id = 0  # For continuous history polling

    def compose(self) -> ComposeResult:
        with Container(classes="app-root"):
            with Horizontal(classes="main-layout"):
                with Vertical(classes="chat-column"):
                    yield ChatLog(
                        id="chat-history",
                        classes="chat-history",
                        highlight=True,
                        markup=True,
                        wrap=True,
                        max_lines=None,
                    )
                    with Horizontal(classes="input-container"):
                        yield Static(">", classes="input-prompt")
                        yield Input(
                            id="chat-input",
                            placeholder="Ask the Hive Mind...  (/help for commands)",
                        )
                with Vertical(classes="sidebar-column"):
                    yield StatusPanel()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        chat = self.query_one("#chat-history", ChatLog)

        # Welcome message
        chat.add_system_message(f"╔═══ {APP_NAME} ═══╗")
        chat.add_system_message(
            f"Version {APP_VERSION} — Hive Mind Client ({CLIENT_TYPE})"
        )
        chat.add_system_message("")

        # Check daemon
        self._check_daemon()

        chat.add_system_message("")
        chat.add_system_message(
            "Type your questions or use /commands. Press /help for commands."
        )
        chat.add_system_message("─" * 40)

        # Focus input
        self.query_one("#chat-input", Input).focus()

        # Fetch initial statuses
        self._check_daemon()
        self._fetch_bridge_status()
        self._load_history()

        # Start continuous background polling
        self.set_interval(3, self._poll_history)
        self.set_interval(5, self._poll_status)

    # ── Daemon Status ────────────────────────────────────────────────────

    @work(thread=False, group="status")
    async def _check_daemon(self) -> None:
        """Check daemon health and update UI."""
        chat = self.query_one("#chat-history", ChatLog)
        health = await daemon_health()

        try:
            daemon_widget = self.query_one("#status-daemon", StatusIndicator)
            llm_widget = self.query_one("#status-llm", StatusIndicator)
            brain_widget = self.query_one("#status-brain", StatusIndicator)
            messages_widget = self.query_one("#status-messages", StatusIndicator)

            if health:
                daemon_widget.set_status("connected")
                llm_widget.set_status(
                    "configured" if health.get("llm_configured") else "missing key"
                )
                brain_widget.set_status(health.get("brain", "idle"))
                messages_widget.set_status(str(health.get("message_count", 0)))
            else:
                daemon_widget.set_status("disconnected")
                llm_widget.set_status("unknown")
        except NoMatches:
            pass

    # ── Bridge Status ────────────────────────────────────────────────────

    async def _bridge_get(self, path: str, timeout: float = 5.0) -> Optional[dict]:
        """Query the bridge API (via daemon's brain)."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BRIDGE_BASE_URL}{path}",
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception:
            return None

    @work(thread=False, group="status")
    async def _fetch_bridge_status(self) -> None:
        """Poll bridge for status info and update sidebar."""
        try:
            bridge_widget = self.query_one("#status-bridge", StatusIndicator)
            phase_widget = self.query_one("#status-phase", StatusIndicator)
            agents_widget = self.query_one("#status-agents", StatusIndicator)
            sep_widget = self.query_one("#status-separation", StatusIndicator)
            all_pairs_widget = self.query_one("#status-all-pairs", StatusIndicator)
            tourn_widget = self.query_one("#status-tournament", StatusIndicator)
        except NoMatches:
            return

        # Check bridge health
        health = await self._bridge_get("/health")
        if health:
            bridge_widget.set_status("connected")
        else:
            bridge_widget.set_status("disconnected")
            return

        # Phase/coherence
        phase_data = await self._bridge_get("/agent/protocol-coherence-status")
        if phase_data:
            ac = phase_data.get("agent_count", "?")
            phase_widget.set_status(f"Phase ~{ac}")

        # Agents
        agent_data = await self._bridge_get("/agent/context-integrity-status")
        if agent_data:
            agents_widget.set_status(f"{agent_data.get('registered_count', '?')} active")

        # Separation
        sep_data = await self._bridge_get("/agent/separation-defensibility-status")
        if sep_data:
            ratio = sep_data.get("ratio", 0)
            sep_widget.set_status(f"{ratio:.3f}")
            all_pairs_widget.set_status(
                "✓ All >1.0" if sep_data.get("all_pairs_above_1") else "✗ Blocker"
            )
        else:
            ait_data = await self._bridge_get("/agent/ait-separation-status")
            if ait_data:
                ratio = ait_data.get("separation_ratio", 0)
                sep_widget.set_status(f"{ratio:.3f}")
                all_pairs_widget.set_status(
                    "✓ All >1.0" if ait_data.get("all_pairs_above_1") else "✗ Below 1.0"
                )

        # Tournament
        preflight = await self._bridge_get("/agent/tournament-preflight-status")
        if preflight:
            ok = preflight.get("overall_pass", False)
            tourn_widget.set_status("✓ Ready" if ok else "✗ Blocked")

    # ── Load history from daemon ─────────────────────────────────────────

    @work(thread=False, group="history")
    async def _load_history(self) -> None:
        """Load conversation history from daemon memory."""
        chat = self.query_one("#chat-history", ChatLog)
        messages = await daemon_get_all_history()
        if messages:
            # Set last_seen_id to the most recent message
            self._last_seen_id = max(m.get("id", 0) for m in messages)
            chat.add_system_message(f"Loaded {len(messages)} messages from shared daemon memory.")
            # Show last 5
            recent = messages[-5:]
            for msg in recent:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    chat.add_user_message(content)
                elif role == "assistant":
                    chat.add_ai_message(content)

    # ── Continuous Background Polling ──────────────────────────────────

    def _poll_history(self) -> None:
        """Continuously poll /history for new messages from other clients.
        Called by set_interval every 3 seconds. Uses _last_seen_id to
        avoid re-displaying messages already shown.
        """
        self._do_poll_history()

    @work(thread=False, group="poll")
    async def _do_poll_history(self) -> None:
        """Async worker for polling history."""
        try:
            messages = await daemon_get_history(since_id=self._last_seen_id)
            if not messages:
                return

            # Update last_seen_id
            self._last_seen_id = max(
                self._last_seen_id,
                max(m.get("id", 0) for m in messages),
            )

            # Display new assistant messages from other clients
            chat = self.query_one("#chat-history", ChatLog)
            for m in messages:
                role = m.get("role", "")
                content = m.get("content", "")
                if not content:
                    continue
                if role == "assistant":
                    chat.add_ai_message(content)
                elif role == "user":
                    # Only show other clients' messages
                    # (ours are displayed by _send_to_daemon)
                    pass
        except Exception:
            pass

    def _poll_status(self) -> None:
        """Continuously poll /status to update sidebar.
        Called by set_interval every 5 seconds.
        """
        self._do_poll_status()

    @work(thread=False, group="poll")
    async def _do_poll_status(self) -> None:
        """Async worker for polling status."""
        try:
            status = await daemon_get_status()
            if not status:
                return

            # Update sidebar indicators
            try:
                brain_widget = self.query_one("#status-brain", StatusIndicator)
                messages_widget = self.query_one("#status-messages", StatusIndicator)

                brain_widget.set_status(status.get("brain_status", "unknown"))
                messages_widget.set_status(str(status.get("message_count", 0)))
            except NoMatches:
                pass
        except Exception:
            pass

    # ── Input Handling ───────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        user_text = event.value.strip()
        if not user_text:
            return

        input_widget = self.query_one("#chat-input", Input)
        input_widget.clear()

        # Check for slash commands
        if user_text.startswith("/"):
            self._handle_command(user_text)
            return

        # Send to daemon
        self._send_to_daemon(user_text)

    def _handle_command(self, cmd: str) -> None:
        """Process a slash command."""
        parts = cmd.lower().split()
        command = parts[0] if parts else "/help"
        chat = self.query_one("#chat-history", ChatLog)

        # Commands handled locally
        if command == "/help":
            self.push_screen(HelpScreen())
        elif command == "/clear":
            self._clear_chat()
        elif command == "/export":
            self._export_chat()
        elif command == "/daemon":
            chat.add_system_message("Fetching daemon status...")
            self._fetch_daemon_status_detailed()
        elif command == "/history":
            chat.add_system_message("Fetching shared history...")
            self._show_daemon_history()
        else:
            # ALL other commands forwarded to daemon brain
            chat.add_system_message(f"Forwarding '{cmd}' to daemon brain...")
            self._send_to_daemon(cmd)

    @work(thread=False, group="daemon")
    async def _fetch_daemon_status_detailed(self) -> None:
        """Show daemon detailed status."""
        chat = self.query_one("#chat-history", ChatLog)
        status = await daemon_get_status()
        health = await daemon_health()

        if not status and not health:
            chat.add_error_message(f"Daemon offline at {DAEMON_URL}")
            return

        chat.add_system_message("═" * 40)
        chat.add_system_message("  DAEMON STATUS")
        chat.add_system_message(f"  URL: {DAEMON_URL}")
        chat.add_system_message("─" * 40)

        if health:
            for k, v in health.items():
                chat.add_system_message(f"  {k}: {v}")
        if status:
            for k, v in status.items():
                chat.add_system_message(f"  {k}: {v}")
        chat.add_system_message("═" * 40)

    @work(thread=False, group="history")
    async def _show_daemon_history(self) -> None:
        """Show shared history from daemon."""
        chat = self.query_one("#chat-history", ChatLog)
        messages = await daemon_get_all_history()
        if not messages:
            chat.add_system_message("No messages in daemon memory.")
            return
        chat.add_system_message(f"═ Showing {len(messages)} messages from shared memory ═")
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                chat.add_user_message(content)
            elif role == "assistant":
                chat.add_ai_message(content)
        chat.add_system_message(f"═ End of history ═")

    # ── Chat with Daemon ─────────────────────────────────────────────────

    @work(thread=False, group="ai")
    async def _send_to_daemon(self, user_text: str) -> None:
        """Send user message to the daemon brain and display response."""
        if self._response_in_progress:
            self.query_one("#chat-history", ChatLog).add_system_message(
                "⚠ Response in progress — please wait."
            )
            return

        chat = self.query_one("#chat-history", ChatLog)
        chat.add_user_message(user_text)

        self._response_in_progress = True

        try:
            chat.add_brain_status("thinking")

            # Send to daemon — blocks until full autonomous tool loop completes
            result = await daemon_send_message(user_text, timeout=120.0)

            # Clear the "thinking" line
            # (Textual doesn't have \033[1A\033[K, so we can't easily remove it)

            if result is None:
                chat.add_error_message(
                    "Daemon did not respond. Check that qortroller_daemon.py "
                    f"is running on {DAEMON_URL}."
                )
                return

            response = result.get("response", "")
            tool_iters = result.get("tool_iterations", 0)

            if not response:
                chat.add_error_message("Daemon returned an empty response.")
                return

            # Display the AI's response
            chat.add_ai_message(response)

            # Track message_id so continuous poller doesn't re-show it
            msg_id = result.get("message_id", 0)
            if msg_id > self._last_seen_id:
                self._last_seen_id = msg_id

            # Show tool usage info
            if tool_iters and tool_iters > 1:
                chat.add_system_message(
                    f"(Used {tool_iters - 1} tool iteration(s) to compose this response)"
                )

            # Update sidebar status (also done by continuous _poll_status)
            try:
                messages_widget = self.query_one("#status-messages", StatusIndicator)
                health = await daemon_health()
                if health:
                    messages_widget.set_status(str(health.get("message_count", "?")))
                    brain_widget = self.query_one("#status-brain", StatusIndicator)
                    brain_widget.set_status("idle")
            except NoMatches:
                pass

        except Exception as e:
            chat.add_error_message(f"Error communicating with daemon: {e}")
        finally:
            self._response_in_progress = False

    # ── Utility Methods ──────────────────────────────────────────────────

    def action_focus_input(self) -> None:
        """Focus the chat input."""
        try:
            self.query_one("#chat-input", Input).focus()
        except NoMatches:
            pass

    def action_clear_chat(self) -> None:
        """Clear chat history."""
        self._clear_chat()

    def _clear_chat(self) -> None:
        """Clear the chat display (local only — daemon memory is preserved)."""
        chat = self.query_one("#chat-history", ChatLog)
        chat.clear()
        chat.add_system_message(
            "Chat display cleared. Daemon memory preserved — use /history to reload."
        )

    def action_export_chat(self) -> None:
        """Export conversation to file."""
        self._export_chat()

    def _export_chat(self) -> None:
        """Save current conversation to a file."""
        chat = self.query_one("#chat-history", ChatLog)
        try:
            export_dir = Path.cwd() / "tui_exports"
            export_dir.mkdir(exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = export_dir / f"qortroller_chat_{timestamp}.json"

            export_data = {
                "app": APP_NAME,
                "version": APP_VERSION,
                "client_type": CLIENT_TYPE,
                "exported_at": datetime.datetime.now().isoformat(),
                "daemon_url": DAEMON_URL,
            }

            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, default=str)

            chat.add_system_message(f"✓ Conversation exported to {export_path}")
        except Exception as e:
            chat.add_error_message(f"Export failed: {e}")

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Launch the QorTroller TUI Hive Mind client."""
    app = QorTrollerTUI()
    app.run()


if __name__ == "__main__":
    main()