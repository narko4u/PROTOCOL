#!/usr/bin/env python3
"""
PROTOCOL CLI — One-command agent operating system launcher.

Usage:
    protocol start       Start all 6 PROTOCOL modules
    protocol stop        Stop all running PROTOCOL modules
    protocol status      Check which modules are running
    protocol publish     Deploy static site (dashboard + landing page)
    protocol version     Show version information

Each module runs as a separate background process:

  Port  Module         Description
  ────  ────────────   ─────────────────────────────
  8500  MEMSTORE       Persistent agent memory
  8501  TRAKR          Cryptographic audit trail
  8502  GUARDRAIL      Policy & governance engine
  8503  VITALS         Observability & telemetry
  8504  HEALER         Autonomous incident recovery
  8505  ORCHESTRATOR   Multi-framework runtime
"""

import os
import signal
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

MODULES = [
    ("MEMSTORE", 8500, "memstore_server.py"),
    ("TRAKR", 8501, "trakr_server.py"),
    ("GUARDRAIL", 8502, "guardrail_server.py"),
    ("VITALS", 8503, "vitals_server.py"),
    ("HEALER", 8504, "healer_server.py"),
    ("ORCHESTRATOR", 8505, "orchestrator_server.py"),
]

COLORS = {
    "green": "\033[0;32m",
    "blue": "\033[0;34m",
    "yellow": "\033[1;33m",
    "red": "\033[0;31m",
    "bold": "\033[1m",
    "nc": "\033[0m",
}


def get_base_dir():
    """Get the PROTOCOL package directory (where server scripts live)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_port(port):
    """Check if a port is in use."""
    try:
        req = Request(f"http://127.0.0.1:{port}/health", method="GET")
        with urlopen(req, timeout=1) as resp:
            return True
    except Exception:
        return False


def check_modules():
    """Check which modules are running."""
    results = []
    for name, port, _ in MODULES:
        running = check_port(port)
        results.append((name, port, running))
    return results


def cmd_start():
    """Start all PROTOCOL modules."""
    base_dir = get_base_dir()
    pids = []

    print(f"{COLORS['blue']}╔══════════════════════════════════════════════╗{COLORS['nc']}")
    print(f"{COLORS['blue']}║  {COLORS['bold']}PROTOCOL v0.2.0{COLORS['nc']}{COLORS['blue']} — Agent Operating System  ║{COLORS['nc']}")
    print(f"{COLORS['blue']}╚══════════════════════════════════════════════╝{COLORS['nc']}")
    print()

    # Clean databases
    for f in os.listdir(base_dir):
        if f.endswith(".db"):
            os.remove(os.path.join(base_dir, f))
    print(f"  {COLORS['green']}✓{COLORS['nc']} Databases reset")

    for name, port, script in MODULES:
        script_path = os.path.join(base_dir, script)
        if not os.path.exists(script_path):
            print(f"  {COLORS['red']}✗{COLORS['nc']} {script} not found — skipping {name}")
            continue

        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        pids.append(proc.pid)
        print(f"  {COLORS['green']}✓{COLORS['nc']} {name} (port {port}) — PID {proc.pid}")
        time.sleep(0.3)

    print()
    print(f"{COLORS['green']}{COLORS['bold']}All modules started.{COLORS['nc']}")
    print(f"  ORCHESTRATOR health: http://127.0.0.1:8505/health")
    print(f"  Module status:       http://127.0.0.1:8505/modules")


def cmd_stop():
    """Stop all running PROTOCOL modules."""
    for name, port, _ in MODULES:
        if check_port(port):
            # Try health endpoint to get PID — kill by port
            try:
                # Use fuser to find and kill processes on the port
                subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3
                )
                print(f"  {COLORS['red']}✗{COLORS['nc']} {name} (port {port}) — stopped")
            except Exception:
                print(f"  {COLORS['yellow']}?{COLORS['nc']} {name} (port {port}) — could not stop")
        else:
            print(f"  {COLORS['yellow']}-{COLORS['nc']} {name} (port {port}) — not running")
    print(f"{COLORS['green']}All modules stopped.{COLORS['nc']}")


def cmd_status():
    """Show which modules are running."""
    results = check_modules()
    all_running = all(r[2] for r in results)

    print(f"PROTOCOL v0.2.0 — Module Status")
    print()
    for name, port, running in results:
        icon = f"{COLORS['green']}●{COLORS['nc']}" if running else f"{COLORS['red']}○{COLORS['nc']}"
        print(f"  {icon} {name:12s}  :{port}")
    print()
    if all_running:
        print(f"  {COLORS['green']}All modules running.{COLORS['nc']}")
    else:
        print(f"  {COLORS['yellow']}Some modules are down. Run 'protocol start'.{COLORS['nc']}")


def cmd_version():
    """Show version information."""
    from protocol import __version__
    print(f"PROTOCOL v{__version__}")
    print(f"Copyright (c) 2026 Empire Labs Pty Ltd")
    print(f"License: MIT")
    print(f"6 modules: MEMSTORE, TRAKR, GUARDRAIL, VITALS, HEALER, ORCHESTRATOR")


USAGE = """PROTOCOL — Agent Operating System

Usage:
    protocol start       Start all 6 modules
    protocol stop        Stop all modules
    protocol status      Check module health
    protocol version     Show version

Each module runs as a separate process:
    8500  MEMSTORE      8501  TRAKR
    8502  GUARDRAIL     8503  VITALS
    8504  HEALER        8505  ORCHESTRATOR

Example:
    protocol start
    curl http://127.0.0.1:8505/health
    protocol status
    protocol stop
"""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(USAGE)
        return

    command = sys.argv[1]

    if command == "start":
        cmd_start()
    elif command == "stop":
        cmd_stop()
    elif command == "status":
        cmd_status()
    elif command == "version":
        cmd_version()
    else:
        print(f"Unknown command: {command}")
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
