# Quickstart

Zero to a working query in under 10 minutes. You'll need Docker and an OpenAI API key.

## 1. Clone and configure

```bash
git clone https://github.com/kartikeyrajvaidya/context-ingest-api.git
cd context-ingest-api
cp .env.example .env
```

Open `.env` and set your OpenAI key:

```
OPENAI_API_KEY=sk-...
```

Everything else has sensible defaults.

## 2. Start the stack

```bash
docker compose up --build -d
```

This starts PostgreSQL (port 5433) and the API (port 8050), runs migrations, and boots the server.

Verify it's alive:

```bash
curl http://localhost:8050/health
```

## 3. Ingest content

The demo corpus is already configured in `data/sources.json`. Ingest it:

```bash
docker compose exec context-ingest-api python -m scripts.ingest_all
```

You'll see output like:

```
ingested=2 unchanged=0 failed=0
```

You can also trigger ingestion over HTTP:

```bash
curl -X POST http://localhost:8050/v1/ingest
```

## 4. Ask a question

```bash
curl -s -X POST http://localhost:8050/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are microservices?", "session_id": "demo"}' | python3 -m json.tool
```

You'll get back an answer with citations, confidence score, and suggested follow-ups.

## 5. Record feedback

```bash
curl -X POST http://localhost:8050/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"query_id": "PASTE_QUERY_ID_HERE", "rating": "helpful"}'
```

Returns `204 No Content`.

## What's next

- [Ingestion guide](./ingestion.md) — add your own content
- [Self-hosting guide](./self-hosting.md) — deploy to your own server
- [Tuning guide](./tuning-retrieval.md) — adjust retrieval quality
- [API contracts](../api/) — full request/response specs
