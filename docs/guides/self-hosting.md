# Self-Hosting Guide

Deploy ContextIngest API on your own server.

## Prerequisites

- Docker and Docker Compose
- An OpenAI API key
- A server with at least 1 GB RAM

## Environment variables

Copy `.env.example` to `.env` and configure:

### Required

| Var | Purpose |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI key. Used for embeddings and answer generation. |
| `POSTGRES_PASSWORD` | Change from the default `password` in production. |

### Database

| Var | Default | Purpose |
|---|---|---|
| `DB_CONNECTION_URI_ASYNCPG` | `postgresql+asyncpg://postgres:password@postgres:5432/context_ingest` | SQLAlchemy async connection string (Docker uses `DOCKER_DB_CONNECTION_URI_ASYNCPG`). |
| `DB_STATEMENT_TIMEOUT` | 3000 | Query timeout in ms. |

### LLM and embeddings

| Var | Default | Purpose |
|---|---|---|
| `OPENAI_ANSWER_MODEL` | gpt-5.4-mini | Model for answer generation. |
| `OPENAI_EMBEDDING_MODEL` | text-embedding-3-small | Embedding model. Change requires reembed. |
| `OPENAI_TIMEOUT_SECONDS` | 20 | LLM call timeout. |

### Rate limiting

| Var | Default | Purpose |
|---|---|---|
| `RATE_LIMIT_IP_PER_MINUTE` | 5 | Max requests per IP per minute (query + feedback). |
| `RATE_LIMIT_SESSION_PER_HOUR` | 15 | Max queries per session per hour. |
| `RATE_LIMIT_CONVERSATION_MAX_TURNS` | 10 | Max turns per conversation. |

### Safety

| Var | Default | Purpose |
|---|---|---|
| `SAFETY_ENABLED` | true | Enable pre-LLM safety gate. Set `false` to disable. |
| `SAFETY_LLM_MODEL` | gpt-4o-mini | Cheap model for safety classification. |

## Reverse proxy

Put a reverse proxy (nginx, Caddy) in front of port 8080 for TLS. Set `X-Forwarded-For` so the rate limiter sees real client IPs:

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header Host $host;
}
```

The rate limiter checks `cf-connecting-ip` (Cloudflare) first, then `X-Forwarded-For`, then `request.client.host`.

## Backups

All state is in PostgreSQL. Back up the `context_ingest` database with standard tools:

```bash
docker compose exec postgres pg_dump -U postgres context_ingest > backup.sql
```

The `query_requests` + `query_responses` tables are your audit trail. The `feedback` table is your quality signal. `documents` + `chunks` can be rebuilt from source via re-ingestion.

## Upgrades

```bash
git pull
docker compose up --build -d
```

Migrations run automatically on boot. Check `db/migrations/sql/` for what changed.

## OpenAI costs

Rough estimates per 1000 operations:

- **Ingestion:** ~$0.01 per document (embedding, varies by length)
- **Queries:** ~$0.005 per query (one embedding + one LLM call)
- **Safety classifier:** ~$0.0003 per query (cheap model, short prompt)

Monitor usage at [platform.openai.com/usage](https://platform.openai.com/usage).

## What this guide does not cover

- TLS certificate provisioning (use Let's Encrypt / Cloudflare)
- Kubernetes deployment
- Cloud-provider-specific setup (AWS, GCP, Azure)
- Authentication (v0 ships without auth — use your reverse proxy)

## Related

- [Quickstart](./quickstart.md) — get running locally first
- [Ingestion guide](./ingestion.md) — add your content
- [Architecture overview](../architecture/overview.md) — how the system works
