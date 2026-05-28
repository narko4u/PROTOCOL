#!/usr/bin/env python3
"""
TRAKR — Cryptographic Agent Audit Trail (Token-Auth)
PROTOCOL Module 2

Requires X-Agent-Token header or 'token' field in request body.
Tokens verified against ORCHESTRATOR (port 8505).
"""

import hashlib
import json
import os
import sqlite3
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from protocol_auth import verify_request

# ─── Configuration ───────────────────────────────────────────────────────────

PORT = int(os.environ.get("TRAKR_PORT", 8501))
DB_PATH = os.environ.get("TRAKR_DB", os.path.join(os.path.dirname(__file__), "trakr.db"))

# ─── Merkle Chain ────────────────────────────────────────────────────────────

def hash_block(previous_hash, action_data, timestamp, nonce=""):
    raw = f"{previous_hash}|{json.dumps(action_data, sort_keys=True)}|{timestamp}|{nonce}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ─── Database ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            session_id TEXT,
            block_index INTEGER NOT NULL,
            previous_hash TEXT NOT NULL,
            action_data TEXT NOT NULL,
            hash TEXT NOT NULL UNIQUE,
            timestamp REAL NOT NULL,
            nonce TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trakr_agent
        ON blocks(agent_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trakr_agent_session
        ON blocks(agent_id, session_id)
    """)
    conn.commit()
    conn.close()

def get_tip(conn, agent_id):
    row = conn.execute(
        "SELECT hash FROM blocks WHERE agent_id = ? ORDER BY block_index DESC LIMIT 1",
        (agent_id,)
    ).fetchone()
    return row[0] if row else None

def get_block_count(conn, agent_id):
    row = conn.execute(
        "SELECT COUNT(*) FROM blocks WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    return row[0] if row else 0

# ─── HTTP Server ──────────────────────────────────────────────────────────────

class TrakrHandler(BaseHTTPRequestHandler):
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
        params = parse_qs(parsed.query)

        if path == "/health":
            conn = sqlite3.connect(DB_PATH)
            count = conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
            conn.close()
            return self._json_response(200, {
                "status": "ok",
                "module": "TRAKR",
                "version": "0.2.0",
                "blocks": count
            })

        elif path == "/chain":
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            limit = int(params.get("limit", [50])[0])
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT id, block_index, previous_hash, action_data, hash, timestamp, session_id "
                "FROM blocks WHERE agent_id = ? ORDER BY block_index DESC LIMIT ?",
                (agent_id, limit)
            ).fetchall()
            conn.close()
            blocks = []
            for r in rows:
                blocks.append({
                    "id": r[0], "block_index": r[1], "previous_hash": r[2],
                    "action_data": json.loads(r[3]), "hash": r[4],
                    "timestamp": r[5], "session_id": r[6]
                })
            return self._json_response(200, {"agent_id": agent_id, "blocks": blocks, "count": len(blocks)})

        elif path == "/verify":
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT block_index, previous_hash, action_data, hash, timestamp "
                "FROM blocks WHERE agent_id = ? ORDER BY block_index ASC",
                (agent_id,)
            ).fetchall()
            conn.close()
            if not rows:
                return self._json_response(200, {"agent_id": agent_id, "verified": True, "blocks_checked": 0, "errors": []})
            errors = []
            for i, r in enumerate(rows):
                idx, prev_hash, action_data, stored_hash, ts = r
                action = json.loads(action_data)
                expected = hash_block(prev_hash, action, ts)
                if expected != stored_hash:
                    errors.append({"block_index": idx, "expected": expected, "stored": stored_hash})
            return self._json_response(200, {"agent_id": agent_id, "verified": len(errors) == 0, "blocks_checked": len(rows), "errors": errors})

        elif path == "/export":
            token = params.get("token", [self.headers.get("X-Agent-Token")])[0]
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            conn = sqlite3.connect(DB_PATH)
            if agent_id:
                rows = conn.execute(
                    "SELECT block_index, previous_hash, action_data, hash, timestamp, session_id "
                    "FROM blocks WHERE agent_id = ? ORDER BY block_index ASC", (agent_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT block_index, previous_hash, action_data, hash, timestamp, session_id "
                    "FROM blocks ORDER BY block_index ASC"
                ).fetchall()
            conn.close()
            records = []
            for r in rows:
                records.append({
                    "trakr_version": "0.2.0", "block_index": r[0], "previous_hash": r[1],
                    "action": json.loads(r[2]), "hash": r[3], "timestamp": r[4], "session_id": r[5]
                })
            self.send_response(200)
            self.send_header("Content-Type", "application/jsonl")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Disposition", "attachment; filename=trakr_export.jsonl")
            self.end_headers()
            for rec in records:
                self.wfile.write((json.dumps(rec) + "\n").encode())

        else:
            return self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/record":
            body = self._read_body()
            token = self._get_token(body)
            agent_id, error = verify_request(token)
            if error:
                return self._json_response(403, {"error": error})
            session_id = body.get("session_id", str(uuid.uuid4()))
            action = body.get("action")
            payload = body.get("payload", {})
            if not action:
                return self._json_response(400, {"error": "action required"})

            conn = sqlite3.connect(DB_PATH)
            block_index = get_block_count(conn, agent_id)
            previous_hash = get_tip(conn, agent_id) or "0" * 64
            timestamp = time.time()
            action_data = {"action": action, "payload": payload, "agent_id": agent_id, "session_id": session_id}
            block_hash = hash_block(previous_hash, action_data, timestamp)
            block_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO blocks (id, agent_id, session_id, block_index, previous_hash, action_data, hash, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (block_id, agent_id, session_id, block_index, previous_hash,
                 json.dumps(action_data), block_hash, timestamp)
            )
            conn.commit()
            conn.close()
            return self._json_response(200, {
                "status": "recorded", "block_id": block_id, "block_index": block_index,
                "hash": block_hash, "previous_hash": previous_hash, "timestamp": timestamp
            })

        else:
            return self._json_response(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    server = HTTPServer(("127.0.0.1", PORT), TrakrHandler)
    print(f"📜 TRAKR v0.2.0 — Token-Auth Audit Trail")
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
