# Database Connection Guide

**Reference:** [Supabase Connection Pooling](https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler)

## Overview

SwiftBolt ML uses:

1. **Supabase REST API** (default) — via `supabase_db.py` and `create_client()`. Uses pooler by default.
2. **Direct Postgres** — via `db.py` for backfills and scripts that need raw SQL.

## Connection Pooler (Recommended for Direct Postgres)

Postgres connections are expensive (1–3MB RAM each). Use the Supabase pooler when connecting directly:

| Connection Type | Port | Use Case |
|----------------|------|----------|
| **Pooler** (transaction mode) | 6543 | App connections, short-lived queries |
| **Direct** | 5432 | Migrations, long-running admin tasks |

### Environment Variables

- `SUPABASE_DB_POOLER_URL` — Pooler URL (preferred)
- `DATABASE_POOLER_URL` — Alternative pooler URL
- `DATABASE_URL` — Direct connection (fallback)

`ml/config/settings.py` uses `effective_database_url`, which prefers the pooler when set.

## Configuration

```python
# settings.effective_database_url returns:
# 1. database_pooler_url (or SUPABASE_DB_POOLER_URL env)
# 2. database_url (or DATABASE_URL env)
```

## Supabase Dashboard

In Supabase Dashboard → Settings → Database, you'll find:

- **Connection string** (direct, port 5432)
- **Connection pooling** (pooler, port 6543)

Use the pooler string for `SUPABASE_DB_POOLER_URL` in production.
