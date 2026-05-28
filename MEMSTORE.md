# MEMSTORE — Persistent Agent Memory

The first PROTOCOL module.

## What it does

MEMSTORE gives AI agents persistent memory that survives between sessions. Instead of rebuilding context from scratch on every startup, agents query MEMSTORE for relevant history — past conversations, learned preferences, ongoing workflows.

## Memory tiers

| Tier | Storage | Retention | Use case |
|------|---------|-----------|----------|
| Working | In-memory (dict) | Session only | Active context |
| Short-term | Redis | 24 hours | Recent conversations |
| Long-term | PostgreSQL + pgvector | Forever | Learned knowledge, user preferences |

## API

```
POST   /memstore/save          Save a memory entry
GET    /memstore/retrieve      Retrieve relevant memories by query
DELETE /memstore/clear         Clear session memories (not long-term)
GET    /memstore/stats         Memory usage statistics
```

## Status

**Building.** Week 1 of the build sprint.
