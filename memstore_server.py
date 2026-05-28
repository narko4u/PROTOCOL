#!/usr/bin/env python3
"""
MEMSTORE — Persistent Agent Memory Layer (Token-Auth)
PROTOCOL Module 1

Requires X-Agent-Token header or 'token' field in request body.
Tokens are verified against ORCHESTRATOR (port 8505).

Endpoints:
  POST   /save       Save a memory entry (requires token)
  GET    /retrieve   Retrieve relevant memories (requires token)
  DELETE /clear      Clear session memories (requires token)
  GET    /stats      Memory usage statistics (no auth)
  GET    /health     Health check (no auth)
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

PORT = int(os.environ.get("MEMSTORE_PORT", 8500))
DB_PATH = os.environ.get("MEMSTORE_DB", os.path.join(os.path.dirname(__file__), "memstore.db"))
WORKING_MEMORY_LIMIT = 100

# ─── In-memory working store ─────────────────────────────────────────────────

working_memory = {}  # {id: {entry}}

# ─── Database ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            session_id TEXT,
            content TEXT NOT NULL,
            embedding BLOB,
            created_at REAL NOT NULL,
            ttl REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_agent
        ON memories(agent_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_created
        ON memories(created_at)
    """)
    conn.commit()
    conn.close()

def save_to_db(agent_id, session_id, content, ttl=None):
    conn = sqlite3.connect(DB_PATH)
    mem_id = str(uuid.uuid4())
    now = time.time()
    conn.execute(
        "INSERT INTO memories (id, agent_id, session_id, content, created_at, ttl) VALUES (?, ?, ?, ?, ?, ?)",
        (mem_id, agent_id, session_id, content, now, ttl)
    )
    conn.commit()
    conn.close()
    return mem_id

def query_db(agent_id, limit=10):
    conn = sqlite3.connect(DB_PATH)
    now = time.time()
    rows = conn.execute(
        "SELECT id, content, created_at FROM memories WHERE agent_id = ? AND (ttl IS NULL OR ttl > ?) ORDER BY created_at DESC LIMIT ?",
        (agent_id, now, limit)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "content": r[1], "created_at": r[2]} for r in rows]

def count_db():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    return count

def clear_db(agent_id=None):
    conn = sqlite3.connect(DB_PATH)
    if agent_id:
        conn.execute("DELETE FROM memories WHERE agent_id = ?", (agent_id,))
    else:
        conn.execute("DELETE FROM memories WHERE ttl IS NOT NULL AND ttl < ?", (time.time(),))
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    return count

# ─── HTTP Server ──────────────────────────────────────────────────────────────

class MemStoreHandler(BaseHTTPRequestHandler):
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
        """Extract token from header or body."""
        token = self.headers.get("X-Agent-Token")
        if not token and body:
            token = body.get("token")
        return token

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Agent-Token")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            return self._json_response(200, {"status": "ok", "module": "MEMSTORE", "version": "0.2.0"})

        elif path == "/stats":
            return self._json_response(200, {
                "working_memory": len(working_memory),
                "working_memory_limit": WORKING_MEMORY_LIMIT,
                "persistent_memory": count_db(),
            })

        elif path == "/retrieve":
            params = parse_qs(parsed.query)
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            limit = int(params.get("limit", [10])[0])
            results = query_db(agent_id, limit)
            working = [v for v in working_memory.values() if v.get("agent_id") == agent_id]
            return self._json_response(200, {
                "agent_id": agent_id,
                "working": working[-5:],
                "persistent": results,
                "total": len(working) + len(results)
            })

        else:
            return self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/save":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            content = body.get("content")
            memory_type = body.get("type", "working")
            ttl = body.get("ttl")

            if not content:
                return self._json_response(400, {"error": "content required"})

            if memory_type == "working":
                mid = str(uuid.uuid4())
                working_memory[mid] = {
                    "id": mid,
                    "agent_id": agent_id,
                    "content": content,
                    "created_at": time.time()
                }
                if len(working_memory) > WORKING_MEMORY_LIMIT:
                    oldest = min(working_memory.keys(), key=lambda k: working_memory[k]["created_at"])
                    del working_memory[oldest]
                return self._json_response(200, {"status": "saved", "type": "working", "id": mid})
            else:
                if memory_type == "short":
                    ttl = ttl or (time.time() + 86400)
                mid = save_to_db(agent_id, body.get("session_id"), content, ttl)
                return self._json_response(200, {"status": "saved", "type": memory_type, "id": mid})

        else:
            return self._json_response(404, {"error": "not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/clear":
            params = parse_qs(parsed.query)
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            remaining = clear_db(agent_id)
            working_memory.clear()
            return self._json_response(200, {
                "status": "cleared",
                "remaining_persistent": remaining,
                "working_memory_cleared": True
            })
        else:
            return self._json_response(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    server = HTTPServer(("127.0.0.1", PORT), MemStoreHandler)
    print(f"🧠 MEMSTORE v0.2.0 — Token-Auth Memory Layer")
    print(f"   Listening on http://127.0.0.1:{PORT}")
    print(f"   Tiers: Working (in-memory) | Short-term (24h DB) | Long-term (persistent)")
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
