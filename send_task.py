#!/usr/bin/env python3
"""
send_task.py — Send a long task to the QorTroller Daemon as ONE message.

Use this when the CLI splits your pasted instruction into multiple messages.
Reads from stdin (or a --file argument) and sends the entire content as a
single POST /chat to the daemon brain.

Usage:
  # Pipe a task directly:
  echo "Build the PoACIngestionAdapter at..." | python send_task.py

  # From a task file:
  python send_task.py --file task.txt

  # Interactive multi-line (type task, then Ctrl+D / Ctrl+Z to send):
  python send_task.py

  # Override daemon URL:
  python send_task.py --daemon http://localhost:8080
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

DAEMON_URL = "http://localhost:8080"


def send(message: str, daemon_url: str = DAEMON_URL, timeout: int = 300) -> str:
    payload = json.dumps({"message": message}).encode()
    req = urllib.request.Request(
        f"{daemon_url}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data.get("response", ""), data.get("tool_iterations", 0)


def main():
    parser = argparse.ArgumentParser(description="Send a task to the daemon brain")
    parser.add_argument("--file", "-f", help="Read task from file instead of stdin")
    parser.add_argument("--daemon", default=DAEMON_URL, help="Daemon URL")
    parser.add_argument("--timeout", type=int, default=300, help="Request timeout (s)")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            message = f.read().strip()
    elif not sys.stdin.isatty():
        message = sys.stdin.read().strip()
    else:
        print("Enter your task (Ctrl+D / Ctrl+Z on empty line to send):")
        print("-" * 60)
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        message = "\n".join(lines).strip()

    if not message:
        print("Error: empty message", file=sys.stderr)
        sys.exit(1)

    print(f"\nSending to {args.daemon}... ({len(message)} chars)", flush=True)
    print("-" * 60)

    response, iterations = send(message, args.daemon, args.timeout)

    print(f"\n[{iterations} tool iteration(s)]\n")
    print(response)


if __name__ == "__main__":
    main()
