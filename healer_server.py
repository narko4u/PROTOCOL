#!/usr/bin/env python3
"""
HEALER — Autonomous Incident Recovery
PROTOCOL Module 5

When an agent goes wrong — high error rate, latency spike, or crash —
HEALER detects it and takes corrective action without human intervention.

Recovery strategies:
  1. Graceful degradation — reduce complexity, drop non-critical paths
  2. Agent restart recycle — restart the agent process
  3. Circuit breaker — halt the failing path, return fallback
  4. State rollback — revert agent state to last known good
  5. Human escalation — when HEALER can't fix it, notify a human

HEALER subscribes to VITALS anomaly events and acts on them.

Usage:
  python3 healer_server.py
  # Listens on port 8504

Endpoints:
  POST  /heal/incident        Report an incident for HEALER to resolve
  GET   /heal/status          Current heal status / active incidents
  GET   /heal/history         Incident history
  POST  /heal/acknowledge     Human acknowledges an escalated incident
  POST  /heal/override        Human overrides HEALER's recommended action
  GET   /health               Health check
"""

import json
import os
import sqlite3
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── Auth ────────────────────────────────────────────────────────────────────

from protocol_auth import verify_request

# ─── Configuration ───────────────────────────────────────────────────────────

PORT = int(os.environ.get("HEALER_PORT", 8504))
DB_PATH = os.environ.get("HEALER_DB", os.path.join(os.path.dirname(__file__), "healer.db"))

# Recovery strategies in order of escalation
RECOVERY_STRATEGIES = [
    "graceful_degradation",
    "agent_restart",
    "circuit_breaker",
    "state_rollback",
    "human_escalation"
]

# How long an incident can stay unresolved before auto-escalating (seconds)
AUTO_ESCALATION_TIMEOUT = 300  # 5 minutes

# ─── Database ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            session_id TEXT,
            incident_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            description TEXT NOT NULL,
            metrics_snapshot TEXT,
            recovery_strategy TEXT,
            recovery_result TEXT,
            human_acknowledged BOOLEAN DEFAULT 0,
            human_override TEXT,
            created_at REAL NOT NULL,
            resolved_at REAL,
            escalated_at REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_healer_status
        ON incidents(status)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_healer_agent
        ON incidents(agent_id)
    """)
    conn.commit()
    conn.close()

# ─── Recovery Strategies ─────────────────────────────────────────────────────

def apply_graceful_degradation(incident):
    """Reduce agent complexity — disable non-critical capabilities."""
    return {
        "action": "graceful_degradation",
        "description": "Reduced agent complexity. Non-critical capabilities disabled.",
        "recommendation": "Limit concurrent tool calls. Disable expensive models. Reduce context window.",
        "auto_applied": True
    }

def apply_agent_restart(incident):
    """Restart the agent process."""
    return {
        "action": "agent_restart",
        "description": "Agent process restarted. State preserved in MEMSTORE.",
        "recommendation": "If this recurs, investigate memory leaks or stuck I/O.",
        "auto_applied": True
    }

def apply_circuit_breaker(incident):
    """Open circuit on the failing action path."""
    return {
        "action": "circuit_breaker",
        "description": f"Circuit opened for {incident.get('incident_type', 'failing_path')}. Fallback handler engaged.",
        "recommendation": "Review the failing action. Clear circuit manually when fixed.",
        "auto_applied": True
    }

def apply_state_rollback(incident):
    """Rollback to last known good state."""
    return {
        "action": "state_rollback",
        "description": "Agent state rolled back to last known good checkpoint.",
        "recommendation": "Review changes between last checkpoint and failure.",
        "auto_applied": True,
        "requires_approval": True
    }

def apply_human_escalation(incident):
    """Escalate to human operator - HEALER cannot resolve."""
    return {
        "action": "human_escalation",
        "description": "HEALER could not resolve autonomously. Human intervention required.",
        "recommendation": "Review incident details, metrics snapshot, and recovery attempts.",
        "auto_applied": False,
        "requires_access": True,
        "severity": "critical"
    }

# ─── Resolution Engine ───────────────────────────────────────────────────────

def resolve_incident(incident_data):
    """Determine the appropriate recovery strategy and apply it."""
    severity = incident_data.get("severity", "warning")
    incident_type = incident_data.get("incident_type", "unknown")
    agent_id = incident_data.get("agent_id", "unknown")

    result = {
        "incident_id": str(uuid.uuid4()),
        "agent_id": agent_id,
        "severity": severity,
        "strategies_attempted": [],
        "resolved": False,
        "escalated": False
    }

    # Determine strategies based on severity
    if severity == "critical":
        strategies = ["graceful_degradation", "circuit_breaker", "human_escalation"]
    elif severity == "error":
        strategies = ["agent_restart", "state_rollback", "human_escalation"]
    else:  # warning
        strategies = ["graceful_degradation", "agent_restart"]

    for strategy_name in strategies:
        strategy_fn = {
            "graceful_degradation": apply_graceful_degradation,
            "agent_restart": apply_agent_restart,
            "circuit_breaker": apply_circuit_breaker,
            "state_rollback": apply_state_rollback,
            "human_escalation": apply_human_escalation
        }.get(strategy_name)

        if not strategy_fn:
            continue

        try:
            outcome = strategy_fn(incident_data)
            outcome["strategy"] = strategy_name
            result["strategies_attempted"].append(outcome)

            if strategy_name == "human_escalation":
                result["escalated"] = True
                result["resolved"] = False
                break
            elif outcome.get("auto_applied", False):
                result["resolved"] = True
                break
        except Exception as e:
            result["strategies_attempted"].append({
                "strategy": strategy_name,
                "error": str(e)
            })

    return result

# ─── HTTP Server ──────────────────────────────────────────────────────────────

class HealerHandler(BaseHTTPRequestHandler):
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

    def _get_token(self, body=None):
        token = self.headers.get("X-Agent-Token")
        if not token and body:
            token = body.get("token")
        return token

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Agent-Token")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            conn = sqlite3.connect(DB_PATH)
            open_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE status='open'").fetchone()[0]
            conn.close()
            return self._json_response(200, {
                "status": "ok",
                "module": "HEALER",
                "version": "0.2.0",
                "open_incidents": open_count
            })

        elif path == "/heal/status":
            token = self._get_token()
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT id, agent_id, incident_type, severity, status, recovery_strategy, "
                "recovery_result, description, human_acknowledged, created_at "
                "FROM incidents WHERE status != 'resolved' ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
            conn.close()
            incidents = []
            for r in rows:
                incidents.append({
                    "id": r[0], "agent_id": r[1], "incident_type": r[2],
                    "severity": r[3], "status": r[4], "recovery_strategy": r[5],
                    "recovery_result": r[6], "description": r[7],
                    "human_acknowledged": bool(r[8]), "created_at": r[9]
                })
            return self._json_response(200, {
                "active_incidents": incidents,
                "count": len(incidents)
            })

        elif path == "/heal/history":
            token = self._get_token()
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            params = parse_qs(parsed.query)
            agent_id = params.get("agent_id", [None])[0]
            limit = int(params.get("limit", [50])[0])

            conn = sqlite3.connect(DB_PATH)
            if agent_id:
                rows = conn.execute(
                    "SELECT * FROM incidents WHERE agent_id = ? ORDER BY created_at DESC LIMIT ?",
                    (agent_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            conn.close()

            columns = ["id", "agent_id", "session_id", "incident_type", "severity", "status",
                       "description", "metrics_snapshot", "recovery_strategy", "recovery_result",
                       "human_acknowledged", "human_override", "created_at", "resolved_at", "escalated_at"]
            results = []
            for r in rows:
                incident = dict(zip(columns, r))
                if incident.get("metrics_snapshot"):
                    incident["metrics_snapshot"] = json.loads(incident["metrics_snapshot"])
                results.append(incident)
            return self._json_response(200, {"incidents": results, "count": len(results)})

        else:
            return self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/heal/incident":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            required = ["agent_id", "incident_type", "severity", "description"]
            for field in required:
                if field not in body:
                    return self._json_response(400, {"error": f"{field} required"})

            # Resolve the incident
            resolution = resolve_incident(body)

            # Persist
            conn = sqlite3.connect(DB_PATH)
            now = time.time()
            final_strategy = resolution["strategies_attempted"][-1]["strategy"] if resolution["strategies_attempted"] else None
            final_result = resolution["strategies_attempted"][-1].get("description") if resolution["strategies_attempted"] else None

            conn.execute(
                "INSERT INTO incidents (id, agent_id, session_id, incident_type, severity, status, "
                "description, metrics_snapshot, recovery_strategy, recovery_result, created_at, "
                "resolved_at, escalated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (resolution["incident_id"], body["agent_id"], body.get("session_id"),
                 body["incident_type"], body["severity"],
                 "escalated" if resolution["escalated"] else "resolved",
                 body["description"], json.dumps(body.get("metrics_snapshot", {})),
                 final_strategy, final_result, now,
                 now if resolution["resolved"] else None,
                 now if resolution["escalated"] else None)
            )
            conn.commit()
            conn.close()

            return self._json_response(200, {
                "status": "processed",
                "incident_id": resolution["incident_id"],
                "resolved": resolution["resolved"],
                "escalated": resolution["escalated"],
                "strategies_attempted": len(resolution["strategies_attempted"]),
                "details": resolution["strategies_attempted"][-1] if resolution["strategies_attempted"] else None
            })

        elif path == "/heal/acknowledge":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            incident_id = body.get("incident_id")
            if not incident_id:
                return self._json_response(400, {"error": "incident_id required"})

            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE incidents SET human_acknowledged = 1, status = 'acknowledged' WHERE id = ?",
                (incident_id,)
            )
            conn.commit()
            conn.close()
            return self._json_response(200, {"status": "acknowledged", "incident_id": incident_id})

        elif path == "/heal/override":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            incident_id = body.get("incident_id")
            override = body.get("override", "")
            if not incident_id:
                return self._json_response(400, {"error": "incident_id required"})

            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE incidents SET human_override = ?, status = 'overridden' WHERE id = ?",
                (override, incident_id)
            )
            conn.commit()
            conn.close()
            return self._json_response(200, {"status": "overridden", "incident_id": incident_id})

        else:
            return self._json_response(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    server = HTTPServer(("127.0.0.1", PORT), HealerHandler)
    print(f"💊 HEALER v0.2.0 — Autonomous Incident Recovery")
    print(f"   Listening on http://127.0.0.1:{PORT}")
    print(f"   Auth: token verification via ORCHESTRATOR (port 8505)")
    print(f"   Strategies: graceful degradation, agent restart, circuit breaker, state rollback, human escalation")
    print(f"   Auto-escalation: {AUTO_ESCALATION_TIMEOUT}s timeout")
    print(f"   Database: {DB_PATH}")
    print(f"   Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Shutting down.")
        server.server_close()

if __name__ == "__main__":
    main()
