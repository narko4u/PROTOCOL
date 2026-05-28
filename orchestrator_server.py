#!/usr/bin/env python3
"""
ORCHESTRATOR — Multi-Framework Agent Runtime with Token Auth
PROTOCOL Module 6

Agent Registration & Token-Based Enforcement:
  Every agent must register via POST /register to receive a session token.
  All other PROTOCOL modules verify this token before serving requests.
  MAX_AGENTS env var controls the cap (default=3, 0=unlimited).

Tier configuration:
  Open Source:  MAX_AGENTS=3
  Pro:          MAX_AGENTS=15
  Enterprise:   MAX_AGENTS=0 (unlimited)

Endpoints:
  POST /register       Register an agent (returns token)
  POST /heartbeat      Refresh agent heartbeat
  GET  /verify         Verify a token (used by other modules)
  GET  /agents         List registered agents
  GET  /status         System status
  GET  /health         Health check
"""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── Configuration ───────────────────────────────────────────────────────────

PORT = int(os.environ.get("ORCHESTRATOR_PORT", 8505))
DB_PATH = os.environ.get("ORCHESTRATOR_DB", os.path.join(os.path.dirname(__file__), "orchestrator.db"))

# Agent cap — 0 = unlimited. This is open source — no artificial limits.
# Users are free to set MAX_AGENTS however they wish.
_MAX_AGENTS_ENV = os.environ.get("MAX_AGENTS", "0")
try:
    MAX_AGENTS = int(_MAX_AGENTS_ENV) if _MAX_AGENTS_ENV != "0" else 0
except ValueError:
    MAX_AGENTS = 3

HEARTBEAT_TTL = 120  # seconds — agent must heartbeat within this or get pruned

# ─── In-memory agent registry ────────────────────────────────────────────────

active_agents = {}  # {token: {agent_id, framework, registered_at, last_heartbeat}}
active_lock = threading.Lock()

# ─── Database ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            token TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            framework TEXT DEFAULT 'custom',
            created_at REAL NOT NULL,
            last_heartbeat REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_reg_agent
        ON registrations(agent_id)
    """)
    conn.commit()
    conn.close()

# ─── Token Management ─────────────────────────────────────────────────────────

def generate_token(agent_id, framework):
    """Generate a unique session token for the agent."""
    raw = f"{agent_id}|{framework}|{time.time()}|{secrets.token_hex(16)}"
    prefix = uuid.uuid5(uuid.NAMESPACE_DNS, raw).hex[:8]
    body = secrets.token_hex(16)
    sig = hashlib.sha256(f"{prefix}{body}{agent_id}".encode()).hexdigest()[:8]
    return f"ptk_{prefix}_{body}_{sig}"

def register_agent(agent_id, framework="custom"):
    """Register an agent. Returns (token, error)."""
    with active_lock:
        now = time.time()
        # Purge stale heartbeats
        stale = [t for t, a in list(active_agents.items())
                 if now - a["last_heartbeat"] > HEARTBEAT_TTL]
        for t in stale:
            del active_agents[t]

        # Check if this agent already has a registration
        existing = [t for t, a in active_agents.items() if a["agent_id"] == agent_id]
        if existing:
            return existing[0], None

        # Check cap (0 = unlimited)
        if MAX_AGENTS > 0 and len(active_agents) >= MAX_AGENTS:
            return None, f"Agent limit reached ({MAX_AGENTS}). Upgrade to Pro or Enterprise."

        # Generate token and register
        token = generate_token(agent_id, framework)
        active_agents[token] = {
            "agent_id": agent_id,
            "framework": framework,
            "registered_at": now,
            "last_heartbeat": now
        }
        # Persist
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO registrations VALUES (?, ?, ?, ?, ?)",
            (token, agent_id, framework, now, now))
        conn.commit()
        conn.close()
        return token, None

def verify_token(token):
    """Verify a token. Returns (agent_id, error)."""
    if not token:
        return None, "token required"
    with active_lock:
        entry = active_agents.get(token)
        if not entry:
            return None, "invalid token — agent not registered"
        now = time.time()
        if now - entry["last_heartbeat"] > HEARTBEAT_TTL:
            del active_agents[token]
            return None, "token expired — agent heartbeat too old"
        # Passive refresh on verify
        entry["last_heartbeat"] = now
        return entry["agent_id"], None

def get_active_agent_count():
    """Return number of currently registered agents."""
    with active_lock:
        now = time.time()
        stale = [t for t, a in list(active_agents.items())
                 if now - a["last_heartbeat"] > HEARTBEAT_TTL]
        for t in stale:
            del active_agents[t]
        return len(active_agents)

# ─── HTTP Server ──────────────────────────────────────────────────────────────

class OrchestratorHandler(BaseHTTPRequestHandler):
    def _json_response(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return json.loads(self.rfile.read(length))
        return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Agent-Token")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/health":
            return self._json_response(200, {
                "status": "ok",
                "module": "ORCHESTRATOR",
                "version": "0.2.0",
                "max_agents": MAX_AGENTS,
                "active_agents": get_active_agent_count()
            })

        elif path == "/verify":
            token = params.get("token", [None])[0]
            agent_id, error = verify_token(token)
            if error:
                return self._json_response(200, {"valid": False, "error": error})
            return self._json_response(200, {"valid": True, "agent_id": agent_id})

        elif path == "/status":
            count = get_active_agent_count()
            agents_list = []
            with active_lock:
                for t, a in list(active_agents.items()):
                    agents_list.append({
                        "agent_id": a["agent_id"],
                        "framework": a["framework"],
                        "registered_at": a["registered_at"],
                        "last_heartbeat": a["last_heartbeat"]
                    })
            return self._json_response(200, {
                "max_agents": MAX_AGENTS,
                "active_count": count,
                "active_agents": agents_list,
                "heartbeat_ttl": HEARTBEAT_TTL
            })

        elif path == "/agents":
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_token(token)
            if error:
                return self._json_response(403, {"error": error})
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("SELECT token, agent_id, framework, created_at, last_heartbeat FROM registrations ORDER BY created_at DESC").fetchall()
            conn.close()
            agents = [{"agent_id": r[1], "framework": r[2], "created_at": r[3]} for r in rows]
            return self._json_response(200, {"agents": agents, "count": len(agents)})

        else:
            return self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/register":
            body = self._read_body()
            agent_id = body.get("agent_id")
            framework = body.get("framework", "custom")
            if not agent_id:
                return self._json_response(400, {"error": "agent_id required"})
            token, error = register_agent(agent_id, framework)
            if error:
                return self._json_response(429, {"error": error, "max_agents": MAX_AGENTS})
            return self._json_response(200, {
                "status": "registered",
                "token": token,
                "agent_id": agent_id,
                "max_agents": MAX_AGENTS,
                "active_count": get_active_agent_count()
            })

        elif path == "/heartbeat":
            body = self._read_body()
            token = body.get("token") or self.headers.get("X-Agent-Token")
            if not token:
                return self._json_response(400, {"error": "token required"})
            with active_lock:
                entry = active_agents.get(token)
                if not entry:
                    return self._json_response(401, {"error": "invalid token — re-register"})
                entry["last_heartbeat"] = time.time()
                # Also persist
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "UPDATE registrations SET last_heartbeat=? WHERE token=?",
                    (time.time(), token))
                conn.commit()
                conn.close()
            return self._json_response(200, {"status": "heartbeat received", "agent_id": entry["agent_id"]})

        else:
            return self._json_response(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    server = HTTPServer(("127.0.0.1", PORT), OrchestratorHandler)
    tier = "Enterprise (unlimited)" if MAX_AGENTS == 0 else f"Open Source/Pro ({MAX_AGENTS} max)"
    print(f"🔁 ORCHESTRATOR v0.2.0 — Token-Auth Agent Runtime")
    print(f"   Listening on http://127.0.0.1:{PORT}")
    print(f"   Agent cap: {tier} (MAX_AGENTS={MAX_AGENTS})")
    print(f"   Heartbeat TTL: {HEARTBEAT_TTL}s")
    print(f"   Database: {DB_PATH}")
    print(f"   Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Shutting down.")
        server.server_close()

if __name__ == "__main__":
    main()
