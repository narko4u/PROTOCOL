#!/usr/bin/env python3
"""
VITALS — Agent Observability & Telemetry
PROTOCOL Module 4

Real-time metrics, tracing, and anomaly detection for AI agents.
Exposes a Prometheus-compatible metrics endpoint and structured logs.

Features:
  - Action throughput (actions per minute)
  - Latency tracking (p50, p95, p99)
  - Error rate monitoring
  - Active agent/session tracking
  - Token consumption monitoring
  - Prometheus /metrics endpoint
  - Anomaly detection (sudden latency spikes, error rate surges)

Usage:
  python3 vitals_server.py
  # Listens on port 8503

Endpoints:
  POST  /event          Submit a telemetry event
  GET   /metrics        Prometheus-formatted metrics
  GET   /dashboard      Summary dashboard JSON (for UI ingestion)
  GET   /anomalies      Recent anomaly detections
  GET   /health         Health check
"""

import json
import os
import sqlite3
import statistics
import time
import uuid
from collections import defaultdict, deque
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from protocol_auth import verify_request

# ─── Configuration ───────────────────────────────────────────────────────────

PORT = int(os.environ.get("VITALS_PORT", 8503))
DB_PATH = os.environ.get("VITALS_DB", os.path.join(os.path.dirname(__file__), "vitals.db"))

# Rolling window for metrics (in seconds)
METRICS_WINDOW = 300  # 5 minutes
ANOMALY_WINDOW = 60   # 1 minute

# In-memory ring buffers for fast metrics
latency_buffer = deque(maxlen=1000)
error_buffer = deque(maxlen=1000)
action_buffer = deque(maxlen=10000)
token_buffer = deque(maxlen=10000)

# ─── Database ─────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            session_id TEXT,
            event_type TEXT NOT NULL,
            action TEXT,
            latency REAL,
            tokens_used INTEGER,
            success BOOLEAN,
            error TEXT,
            metadata TEXT,
            timestamp REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_vitals_agent
        ON events(agent_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_vitals_timestamp
        ON events(timestamp)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id TEXT PRIMARY KEY,
            agent_id TEXT,
            anomaly_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            value REAL,
            threshold REAL,
            detected_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# ─── Anomaly Detection ───────────────────────────────────────────────────────

def detect_anomalies(agent_id=None):
    """Check for anomalies in recent telemetry data."""
    now = time.time()
    anomalies = []

    # Check latency spike (>3x the p95)
    if len(latency_buffer) > 10:
        recent = [l[0] for l in latency_buffer if l[2] > now - ANOMALY_WINDOW]
        if recent:
            recent_latencies = recent
            avg = statistics.mean(recent_latencies)
            p95 = sorted(recent_latencies)[int(len(recent_latencies) * 0.95)]

            # Compare with historical
            historical = [l[0] for l in latency_buffer if l[2] <= now - ANOMALY_WINDOW]
            if historical:
                hist_p95 = sorted(historical)[int(len(historical) * 0.95)]
                if hist_p95 > 0 and p95 > hist_p95 * 3:
                    anomalies.append({
                        "type": "latency_spike",
                        "severity": "warning",
                        "message": f"Latency spike: current P95={p95:.3f}s vs historical P95={hist_p95:.3f}s",
                        "value": p95,
                        "threshold": hist_p95 * 3
                    })

    # Check error rate surge
    if len(error_buffer) > 20:
        recent_errs = [e for e in error_buffer if e[2] > now - ANOMALY_WINDOW]
        recent_total = len([a for a in action_buffer if a[2] > now - ANOMALY_WINDOW])
        if recent_total > 0:
            error_rate = len(recent_errs) / recent_total
            if error_rate > 0.1:  # >10% error rate
                anomalies.append({
                    "type": "error_surge",
                    "severity": "critical",
                    "message": f"Error rate surge: {error_rate:.1%} in last {ANOMALY_WINDOW}s",
                    "value": error_rate,
                    "threshold": 0.1
                })

    return anomalies

# ─── Metrics Computation ─────────────────────────────────────────────────────

def compute_metrics(agent_id=None):
    """Compute current metrics from ring buffers."""
    now = time.time()
    window_start = now - METRICS_WINDOW

    # Filter by agent if specified
    if agent_id:
        relevant_actions = [a for a in action_buffer if a[0] == agent_id and a[2] > window_start]
        relevant_latency = [l[0] for l in latency_buffer if l[1] == agent_id and l[2] > window_start]
        relevant_errors = [e for e in error_buffer if e[0] == agent_id and e[2] > window_start]
        relevant_tokens = [t[0] for t in token_buffer if t[1] == agent_id and t[2] > window_start]
    else:
        relevant_actions = [a for a in action_buffer if a[2] > window_start]
        relevant_latency = [l[0] for l in latency_buffer if l[2] > window_start]
        relevant_errors = [e for e in error_buffer if e[2] > window_start]
        relevant_tokens = [t[0] for t in token_buffer if t[2] > window_start]

    # Action throughput
    actions_per_min = len(relevant_actions) / (METRICS_WINDOW / 60)

    # Latency stats
    if relevant_latency:
        sorted_lat = sorted(relevant_latency)
        latency_p50 = sorted_lat[len(sorted_lat) // 2]
        latency_p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
        latency_p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
        latency_avg = statistics.mean(sorted_lat)
    else:
        latency_p50 = latency_p95 = latency_p99 = latency_avg = 0.0

    # Error rate
    total_actions = len(relevant_actions) or 1
    error_rate = len(relevant_errors) / total_actions

    # Token usage
    total_tokens = sum(relevant_tokens) if relevant_tokens else 0

    return {
        "latency_p50": round(latency_p50, 3),
        "latency_p95": round(latency_p95, 3),
        "latency_p99": round(latency_p99, 3),
        "latency_avg": round(latency_avg, 3),
        "actions_per_minute": round(actions_per_min, 2),
        "total_actions_window": len(relevant_actions),
        "error_rate": round(error_rate, 4),
        "total_errors_window": len(relevant_errors),
        "total_tokens_window": total_tokens
    }

# ─── HTTP Server ──────────────────────────────────────────────────────────────

class VitalsHandler(BaseHTTPRequestHandler):
    def _json_response(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _text_response(self, status, text):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(text.encode())

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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Agent-Token")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            return self._json_response(200, {
                "status": "ok",
                "module": "VITALS",
                "version": "0.2.0"
            })

        elif path == "/metrics":
            metrics = compute_metrics()
            prometheus = (
                "# HELP protocol_actions_per_minute Action throughput\n"
                f"# TYPE protocol_actions_per_minute gauge\n"
                f"protocol_actions_per_minute {metrics['actions_per_minute']}\n\n"
                "# HELP protocol_latency_p50 Median latency\n"
                f"# TYPE protocol_latency_p50 gauge\n"
                f"protocol_latency_p50 {metrics['latency_p50']}\n\n"
                "# HELP protocol_latency_p95 P95 latency\n"
                f"# TYPE protocol_latency_p95 gauge\n"
                f"protocol_latency_p95 {metrics['latency_p95']}\n\n"
                "# HELP protocol_latency_p99 P99 latency\n"
                f"# TYPE protocol_latency_p99 gauge\n"
                f"protocol_latency_p99 {metrics['latency_p99']}\n\n"
                "# HELP protocol_error_rate Error rate\n"
                f"# TYPE protocol_error_rate gauge\n"
                f"protocol_error_rate {metrics['error_rate']}\n\n"
                "# HELP protocol_total_actions Total actions in window\n"
                f"# TYPE protocol_total_actions counter\n"
                f"protocol_total_actions {metrics['total_actions_window']}\n\n"
                "# HELP protocol_total_errors Total errors in window\n"
                f"# TYPE protocol_total_errors counter\n"
                f"protocol_total_errors {metrics['total_errors_window']}\n\n"
                "# HELP protocol_total_tokens Total tokens consumed in window\n"
                f"# TYPE protocol_total_tokens counter\n"
                f"protocol_total_tokens {metrics['total_tokens_window']}\n"
            )
            return self._text_response(200, prometheus)

        elif path == "/dashboard":
            params = parse_qs(parsed.query)
            agent_id, error = verify_request(self._get_token())
            if error:
                return self._json_response(403, {"error": error})
            agent_id = params.get("agent_id", [None])[0]
            metrics = compute_metrics(agent_id)
            anomalies = detect_anomalies(agent_id)
            return self._json_response(200, {
                "metrics": metrics,
                "anomalies": anomalies,
                "window_seconds": METRICS_WINDOW,
                "generated_at": time.time()
            })

        elif path == "/anomalies":
            agent_id, error = verify_request(self._get_token())
            if error:
                return self._json_response(403, {"error": error})
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT id, agent_id, anomaly_type, severity, message, value, threshold, detected_at "
                "FROM anomalies ORDER BY detected_at DESC LIMIT 20"
            ).fetchall()
            conn.close()
            results = []
            for r in rows:
                results.append({
                    "id": r[0], "agent_id": r[1], "type": r[2],
                    "severity": r[3], "message": r[4],
                    "value": r[5], "threshold": r[6], "detected_at": r[7]
                })
            return self._json_response(200, {"anomalies": results, "count": len(results)})

        else:
            return self._json_response(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/event":
            body = self._read_body()
            agent_id, error = verify_request(self._get_token(body))
            if error:
                return self._json_response(403, {"error": error})
            agent_id = body.get("agent_id", "unknown")
            session_id = body.get("session_id")
            event_type = body.get("event_type", "action")
            action = body.get("action")
            latency = body.get("latency", 0.0)
            tokens_used = body.get("tokens_used", 0)
            success = body.get("success", True)
            error = body.get("error")
            metadata = body.get("metadata", {})

            # Write to ring buffers
            now = time.time()
            action_buffer.append((agent_id, action, now))
            if latency > 0:
                latency_buffer.append((latency, agent_id, now))
            if not success:
                error_buffer.append((agent_id, error, now))
            if tokens_used > 0:
                token_buffer.append((tokens_used, agent_id, now))

            # Write to persistent store
            conn = sqlite3.connect(DB_PATH)
            eid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO events (id, agent_id, session_id, event_type, action, latency, tokens_used, success, error, metadata, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (eid, agent_id, session_id, event_type, action, latency, tokens_used,
                 success, error, json.dumps(metadata), now)
            )
            conn.commit()
            conn.close()

            # Run anomaly detection
            anomalies = detect_anomalies(agent_id)
            for a in anomalies:
                aid = str(uuid.uuid4())
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO anomalies (id, agent_id, anomaly_type, severity, message, value, threshold, detected_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (aid, agent_id, a["type"], a["severity"], a["message"], a["value"], a["threshold"], now)
                )
                conn.commit()
                conn.close()

            return self._json_response(200, {
                "status": "recorded",
                "event_id": eid,
                "anomalies_detected": len(anomalies)
            })

        else:
            return self._json_response(404, {"error": "not found"})

    def log_message(self, format, *args):
        pass

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    init_db()
    server = HTTPServer(("127.0.0.1", PORT), VitalsHandler)
    print(f"📊 VITALS v0.2.0 — Agent Observability & Telemetry")
    print(f"   Listening on http://127.0.0.1:{PORT}")
    print(f"   Metrics: throughput, latency (p50/p95/p99), error rate, tokens")
    print(f"   Prometheus: /metrics endpoint")
    print(f"   Auth: token verification via ORCHESTRATOR (port 8505)")
    print(f"   Anomaly detection: latency spikes, error surges")
    print(f"   Database: {DB_PATH}")
    print(f"   Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Shutting down.")
        server.server_close()

if __name__ == "__main__":
    main()
