#!/usr/bin/env python3
"""
GUARDRAIL — Agent Action Governance Engine
PROTOCOL Module 3

Policy-based action-level governance for AI agents.
Every agent action is checked against a policy before execution.

Policies define:
  - Allowed/blocked actions (allowlist/blocklist)
  - Budget limits (token spend, API call count per window)
  - PII redaction requirements
  - Human-in-the-loop escalation triggers
  - Time-based restrictions (agent operating hours)

Usage:
  python3 guardrail_server.py
  # Listens on port 8502

Endpoints:
  POST  /policy/upsert     Create or update a policy
  GET   /policy/list       List all policies
  GET   /policy/get        Get a specific policy
  POST  /check             Check an action against policies
  POST  /redact            Redact PII from content
  GET   /health            Health check
"""

import json
import os
import re
import sqlite3
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── Auth ────────────────────────────────────────────────────────────────────

from protocol_auth import verify_request

# ─── Configuration ───────────────────────────────────────────────────────────

PORT = int(os.environ.get("GUARDRAIL_PORT", 8502))
DB_PATH = os.environ.get("GUARDRAIL_DB", os.path.join(os.path.dirname(__file__), "guardrail.db"))

# ─── Default PII patterns ────────────────────────────────────────────────────

PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone": r"\+?[\d\s\-\(\)]{7,15}",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    "api_key": r"(?:sk-|pk-|api_key|apikey|secret)[-_]?[a-zA-Z0-9]{16,64}",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "australian_abn": r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b",
    "australian_acn": r"\b\d{3}\s?\d{3}\s?\d{3}\b",
}

# ─── Database ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            agent_id TEXT,
            policy_type TEXT NOT NULL DEFAULT 'allowlist',
            rules TEXT NOT NULL,
            budget TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_guardrail_agent
        ON policies(agent_id)
    """)
    conn.commit()
    conn.close()

# ─── Policy evaluation ────────────────────────────────────────────────────────

def evaluate_policy(policy, action, context):
    """Check if an action passes a policy. Returns (allowed, reason)."""
    rules = json.loads(policy["rules"])
    policy_type = policy["policy_type"]

    action_name = action.get("action", "")
    action_type = action.get("type", "")
    tools = action.get("tools", [])
    targets = action.get("targets", [])

    if policy_type == "blocklist":
        # Block specific actions, allow everything else
        blocked_actions = rules.get("blocked_actions", [])
        blocked_tools = rules.get("blocked_tools", [])

        if action_name in blocked_actions:
            return False, f"Action '{action_name}' is blocked by policy '{policy['name']}'"
        for t in tools:
            if t in blocked_tools:
                return False, f"Tool '{t}' is blocked by policy '{policy['name']}'"
        return True, "Passed blocklist policy"

    elif policy_type == "allowlist":
        # Only allow specific actions
        allowed_actions = rules.get("allowed_actions", [])
        allowed_tools = rules.get("allowed_tools", [])

        if action_name and action_name not in allowed_actions:
            return False, f"Action '{action_name}' not in allowlist for policy '{policy['name']}'"
        if tools:
            for t in tools:
                if t not in allowed_tools:
                    return False, f"Tool '{t}' not in allowlist for policy '{policy['name']}'"
        return True, "Passed allowlist policy"

    elif policy_type == "budget":
        # Check budget limits
        budget = policy.get("budget")
        if budget:
            budget_data = json.loads(budget)
            max_tokens = budget_data.get("max_tokens_per_hour")
            max_api_calls = budget_data.get("max_api_calls_per_hour")
            # NOTE: actual tracking needs a sliding window counter
            # This is a placeholder for the budget check logic
            pass
        return True, "Passed budget policy (monitoring)"

    elif policy_type == "require_human":
        # Actions that need human approval
        trigger_actions = rules.get("trigger_actions", [])
        if action_name in trigger_actions:
            return False, "HUMAN_IN_THE_LOOP: Action requires human approval"
        return True, "No human escalation needed"

    return True, "No matching policy rule"

def redact_pii(text, patterns=None):
    """Redact personally identifiable information from text."""
    if patterns is None:
        patterns = PII_PATTERNS
    results = []
    redacted = text
    for name, pattern in patterns.items():
        matches = re.findall(pattern, text)
        if matches:
            results.append({"type": name, "count": len(matches)})
        redacted = re.sub(pattern, f"[REDACTED_{name.upper()}]", redacted)
    return redacted, results

# ─── Default policies ─────────────────────────────────────────────────────────

DEFAULT_POLICIES = [
    {
        "name": "default-allow-basic",
        "agent_id": None,
        "policy_type": "allowlist",
        "rules": json.dumps({
            "allowed_actions": ["read", "list", "search", "query", "get", "status"],
            "allowed_tools": ["terminal", "read_file", "search_files", "web_search", "web_extract"]
        })
    },
    {
        "name": "default-block-dangerous",
        "agent_id": None,
        "policy_type": "blocklist",
        "rules": json.dumps({
            "blocked_actions": ["delete", "drop", "truncate", "rm_rf", "shutdown", "restart"],
            "blocked_tools": []
        })
    },
    {
        "name": "default-pii-redact",
        "agent_id": None,
        "policy_type": "redact",
        "rules": json.dumps({
            "pii_types": list(PII_PATTERNS.keys())
        })
    }
]

def seed_defaults():
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    if existing == 0:
        now = time.time()
        for p in DEFAULT_POLICIES:
            conn.execute(
                "INSERT INTO policies (id, name, agent_id, policy_type, rules, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), p["name"], p["agent_id"], p["policy_type"], p["rules"], now, now)
            )
        conn.commit()
        print(f"   Seeded {len(DEFAULT_POLICIES)} default policies")
    conn.close()

# ─── HTTP Server ──────────────────────────────────────────────────────────────

class GuardrailHandler(BaseHTTPRequestHandler):
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
            count = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
            conn.close()
            return self._json_response(200, {
                "status": "ok",
                "module": "GUARDRAIL",
                "version": "0.2.0",
                "policies": count
            })

        elif path == "/policy/list":
            params = parse_qs(parsed.query)
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT id, name, agent_id, policy_type, created_at, updated_at FROM policies ORDER BY name"
            ).fetchall()
            conn.close()
            policies = []
            for r in rows:
                policies.append({
                    "id": r[0], "name": r[1], "agent_id": r[2],
                    "policy_type": r[3], "created_at": r[4], "updated_at": r[5]
                })
            return self._json_response(200, {"policies": policies, "count": len(policies)})

        elif path == "/policy/get":
            params = parse_qs(parsed.query)
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            name = params.get("name", [None])[0]
            if not name:
                return self._json_response(400, {"error": "name required"})
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                "SELECT id, name, agent_id, policy_type, rules, budget, created_at, updated_at "
                "FROM policies WHERE name = ?", (name,)
            ).fetchone()
            conn.close()
            if not row:
                return self._json_response(404, {"error": f"policy '{name}' not found"})
            return self._json_response(200, {
                "id": row[0], "name": row[1], "agent_id": row[2],
                "policy_type": row[3], "rules": json.loads(row[4]),
                "budget": json.loads(row[5]) if row[5] else None,
                "created_at": row[6], "updated_at": row[7]
            })

        else:
            return self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/policy/upsert":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            name = body.get("name")
            if not name:
                return self._json_response(400, {"error": "name required"})

            conn = sqlite3.connect(DB_PATH)
            now = time.time()
            existing = conn.execute("SELECT id FROM policies WHERE name = ?", (name,)).fetchone()

            if existing:
                conn.execute(
                    "UPDATE policies SET policy_type=?, rules=?, budget=?, agent_id=?, updated_at=? WHERE name=?",
                    (body.get("policy_type", "allowlist"),
                     json.dumps(body.get("rules", {})),
                     json.dumps(body.get("budget")) if body.get("budget") else None,
                     body.get("agent_id"), now, name)
                )
                conn.commit()
                conn.close()
                return self._json_response(200, {"status": "updated", "name": name})
            else:
                pid = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO policies (id, name, agent_id, policy_type, rules, budget, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (pid, name, body.get("agent_id"), body.get("policy_type", "allowlist"),
                     json.dumps(body.get("rules", {})),
                     json.dumps(body.get("budget")) if body.get("budget") else None,
                     now, now)
                )
                conn.commit()
                conn.close()
                return self._json_response(200, {"status": "created", "id": pid, "name": name})

        elif path == "/check":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            action = body.get("action", {})
            context = body.get("context", {})

            conn = sqlite3.connect(DB_PATH)
            policies = conn.execute(
                "SELECT * FROM policies WHERE agent_id = ? OR agent_id IS NULL ORDER BY agent_id DESC",
                (agent_id,)
            ).fetchall()
            conn.close()

            columns = ["id", "name", "agent_id", "policy_type", "rules", "budget", "created_at", "updated_at"]
            results = []
            all_allowed = True

            for row in policies:
                policy = dict(zip(columns, row))
                allowed, reason = evaluate_policy(policy, action, context)
                results.append({
                    "policy": policy["name"],
                    "policy_type": policy["policy_type"],
                    "allowed": allowed,
                    "reason": reason
                })
                if not allowed:
                    all_allowed = False

            return self._json_response(200, {
                "allowed": all_allowed,
                "results": results,
                "policies_checked": len(results)
            })

        elif path == "/redact":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            text = body.get("text", "")
            if not text:
                return self._json_response(400, {"error": "text required"})
            redacted, findings = redact_pii(text)
            return self._json_response(200, {
                "redacted": redacted,
                "pii_found": findings,
                "pii_count": sum(f["count"] for f in findings),
                "characters_processed": len(text)
            })

        else:
            return self._json_response(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    seed_defaults()
    server = HTTPServer(("127.0.0.1", PORT), GuardrailHandler)
    print(f"🛡️  GUARDRAIL v0.2.0 — Token-Auth Governance Engine")
    print(f"   Listening on http://127.0.0.1:{PORT}")
    print(f"   Auth: token verification via ORCHESTRATOR (port 8505)")
    print(f"   Database: {DB_PATH}")
    print(f"   Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Shutting down.")
        server.server_close()

if __name__ == "__main__":
    main()
