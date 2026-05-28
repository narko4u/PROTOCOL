# VITALS — Agent Observability & Telemetry

The fourth PROTOCOL module.

## What it does

VITALS gives you real-time visibility into every agent in your fleet. Throughput, latency, error rates, token consumption — all streamed into in-memory ring buffers for instant querying and persisted to SQLite for historical analysis.

## Key capabilities

- **Real-time metrics** — action throughput, p50/p95/p99 latency, error rate, token usage
- **Prometheus /metrics endpoint** — drop into any existing monitoring stack (Grafana, Datadog, etc.)
- **Dashboard JSON** — structured data for UI ingestion or programmatic consumption
- **Anomaly detection** — automatic detection of latency spikes (>3x historical p95) and error rate surges (>10%)
- **Rolling window** — default 5-minute window for live metrics, 1-minute for anomaly detection

## API

```
POST  /event              Submit a telemetry event
GET   /metrics            Prometheus-formatted metrics endpoint
GET   /dashboard          Summary dashboard JSON
GET   /anomalies          Recent anomaly detections
GET   /health             Health check
```

## Metrics exposed (Prometheus)

| Metric | Type | Description |
|--------|------|-------------|
| `protocol_actions_per_minute` | gauge | Action throughput |
| `protocol_latency_p50` | gauge | Median latency (seconds) |
| `protocol_latency_p95` | gauge | P95 latency (seconds) |
| `protocol_latency_p99` | gauge | P99 latency (seconds) |
| `protocol_error_rate` | gauge | Proportion of failed actions |
| `protocol_total_actions` | counter | Total actions in window |
| `protocol_total_errors` | counter | Total errors in window |
| `protocol_total_tokens` | counter | Total tokens consumed |

## Anomaly detection

VITALS continuously monitors for:
- **Latency spikes** — when current P95 exceeds 3x the historical P95
- **Error surges** — when error rate exceeds 10% in the last 60 seconds

Detected anomalies are persisted and exposed via `/anomalies` for HEALER to consume.

## Event payload

```json
{
  "agent_id": "sovereign",
  "session_id": "sess-123",
  "event_type": "action",
  "action": "web_search",
  "latency": 1.23,
  "tokens_used": 450,
  "success": true,
  "error": null,
  "metadata": {}
}
```

## Integration

VITALS is designed to pair with HEALER. Submit events → VITALS detects anomalies → HEALER resolves them.

## Status

**Built.**
