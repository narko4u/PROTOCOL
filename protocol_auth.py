"""
protocol_auth.py — Shared token verification for all PROTOCOL modules.

All PROTOCOL modules (MEMSTORE, TRAKR, GUARDRAIL, VITALS, HEALER) import this
and call verify_request(token) at the start of every non-health endpoint.

Usage:
    from protocol_auth import verify_request

    def do_POST(self):
        body = self._read_body()
        token = body.get("token") or self.headers.get("X-Agent-Token")
        agent_id, error = verify_request(token)
        if error:
            return self._json_response(403, {"error": error})
        # ... handle request for agent_id
"""

import json
from urllib.request import Request, urlopen
from urllib.error import URLError

ORCHESTRATOR_URL = "http://127.0.0.1:8505"

# Simple in-memory cache: token -> (agent_id, cached_at)
_verify_cache = {}
_CACHE_TTL = 30  # seconds — re-verify every 30s

def verify_request(token):
    """
    Verify an agent token against the ORCHESTRATOR.
    Returns (agent_id, None) on success, (None, error_msg) on failure.
    Results are cached for 30 seconds to reduce orchestrator load.
    """
    if not token:
        return None, "token required — register via ORCHESTRATOR POST /register"

    # Check cache
    cached = _verify_cache.get(token)
    if cached:
        from time import time
        if time() - cached[1] < _CACHE_TTL:
            return cached[0], None

    # Call orchestrator
    try:
        req = Request(f"{ORCHESTRATOR_URL}/verify?token={token}", method="GET")
        with urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            if data.get("valid"):
                from time import time
                _verify_cache[token] = (data["agent_id"], time())
                return data["agent_id"], None
            return None, data.get("error", "invalid token")
    except URLError as e:
        return None, f"orchestrator unreachable: {e.reason}"
    except Exception as e:
        return None, f"auth error: {str(e)}"


def clear_verify_cache():
    """Clear the verification cache (e.g., on token revocation)."""
    _verify_cache.clear()
