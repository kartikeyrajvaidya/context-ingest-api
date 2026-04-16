# ContextIngest API

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/kartikeyrajvaidya/context-ingest-api/actions/workflows/ci.yml/badge.svg)](https://github.com/kartikeyrajvaidya/context-ingest-api/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](./CODE_OF_CONDUCT.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

> Drop-in RAG backend for your content site. Ingest URLs, ask questions, get cited answers.

**ContextIngest API** is an open-source, self-hosted backend that turns any blog, docs site, or knowledge base into a citation-backed chatbot. Feed it URLs via a manifest file, it ingests them into Postgres, and exposes three HTTP endpoints: **query**, **feedback**, and **ingest**.

No vector database service. No background queue. No framework sprawl. Just FastAPI, Postgres with pgvector, and OpenAI.

> **Status: alpha (`0.1.0a0`)** -- APIs may change before `1.0`. See [CHANGELOG](./CHANGELOG.md).

---

## 30-second start

```bash
git clone https://github.com/kartikeyrajvaidya/context-ingest-api.git
cd context-ingest-api
cp .env.example .env          # set OPENAI_API_KEY
docker compose up --build -d  # Postgres on :5433, API on :8050
```

Ingest the demo corpus and ask a question:

```bash
curl -X POST http://localhost:8050/v1/ingest
curl -s -X POST http://localhost:8050/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are microservices?", "session_id": "demo"}'
```

Full walkthrough: [Quickstart guide](./docs/guides/quickstart.md).

---

## Features

- **Manifest-driven ingestion.** List URLs in `data/sources.json`, hit `POST /v1/ingest` or run the CLI. Rerun-safe via content hashing -- unchanged content is skipped at zero cost.
- **Hybrid retrieval.** Vector search (pgvector HNSW) + full-text search (Postgres tsvector), fused with Reciprocal Rank Fusion.
- **Citation-backed answers.** Every answer returns the chunks and source URLs it was grounded in. Weak retrieval produces an explicit "I don't know" instead of hallucination.
- **Multi-turn conversations.** Pass a `conversation_id` to continue a thread. History is injected into the LLM prompt automatically.
- **Safety gate.** Two-layer pre-LLM filter (regex heuristics + LLM classifier) catches prompt injection and jailbreak attempts. Toggleable via `SAFETY_ENABLED`.
- **Feedback loop.** `POST /v1/feedback` records thumbs up/down per query for quality tracking.
- **One database.** Documents, chunks, embeddings, queries, feedback -- all in Postgres. No Redis, no Pinecone.
- **Rate-limited by default.** Three layers: per-IP, per-session, per-conversation.
- **Docker Compose in one command.** `docker compose up --build -d` gives you everything.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/query` | Ask a question, get a cited answer |
| POST | `/v1/feedback` | Record feedback on a query |
| POST | `/v1/ingest` | Trigger manifest-driven ingestion |
| GET | `/health` | Health check |

See [API contracts](./docs/api/) for full specs.

---

## Stack

| Layer | Choice |
|---|---|
| Web framework | FastAPI (async) |
| Database | PostgreSQL 17 + pgvector |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| Migrations | Alembic + raw SQL |
| Embeddings | OpenAI `text-embedding-3-small` |
| Answer LLM | OpenAI `gpt-5.4-mini` (configurable) |
| Safety LLM | OpenAI `gpt-4o-mini` (configurable) |

---

## Project layout

```
api/          Routes, middleware, error handlers
configs/      Env-driven config classes
core/         Business logic (actions, ingestion, safety, services)
db/           SQLAlchemy models + migrations
libs/         Logger, shared utilities
scripts/      CLI tools (ingest_all, ingest_one, reembed_all)
docs/         Architecture, API contracts, guides
```

---

## Documentation

| I want to... | Read... |
|---|---|
| Get running in 10 minutes | [Quickstart](./docs/guides/quickstart.md) |
| Add my own content | [Ingestion guide](./docs/guides/ingestion.md) |
| Deploy to production | [Self-hosting guide](./docs/guides/self-hosting.md) |
| Improve answer quality | [Tuning guide](./docs/guides/tuning-retrieval.md) |
| Understand the architecture | [Architecture overview](./docs/architecture/overview.md) |
| See the database schema | [Schema](./docs/architecture/schema.md) |
| Understand retrieval | [Retrieval deep-dive](./docs/architecture/retrieval.md) |
| Call the query API | [Query contract](./docs/api/query.md) |
| Call the feedback API | [Feedback contract](./docs/api/feedback.md) |
| Call the ingest API | [Ingest contract](./docs/api/ingest.md) |

---

## What this is not

- **Not a hosted product.** Self-host it or run locally.
- **Not a vector database.** It uses pgvector inside Postgres.
- **Not multi-tenant.** One database, one namespace. Run one instance per tenant if needed.
- **Not authenticated.** v0 ships without auth. Put a reverse proxy in front for access control.

---

## Community

- Questions and ideas -- [GitHub Discussions](https://github.com/kartikeyrajvaidya/context-ingest-api/discussions)
- Bug reports -- [open an issue](https://github.com/kartikeyrajvaidya/context-ingest-api/issues/new/choose)
- Security vulnerabilities -- see [SECURITY.md](./SECURITY.md) (private disclosure)
- Code of Conduct -- [Contributor Covenant 2.1](./CODE_OF_CONDUCT.md)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). PRs welcome.

## License

[MIT](./LICENSE)
