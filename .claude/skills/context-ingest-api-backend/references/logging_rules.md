# Logging Rules

## Logger choice

Use the shared logger pattern:

```python
from libs.logger import get_logger

logger = get_logger(__name__)
```

Keep the logger wrapper simple unless the project explicitly needs structured logging later.

## What to log

- app startup and shutdown
- important business success events (one per request path)
- request failures at the layer that catches them
- DB transaction failures in the transaction helper
- auth failures when auth exists

## What not to log

- API keys
- secrets
- full request bodies by default
- raw user-submitted text content (may contain PII)
- raw upstream payload dumps
- stack traces at multiple layers for the same error

## Success logging rules

- One meaningful success log per request path is enough.
- Prefer logging identifiers and business context, not entire objects.
- Good examples:
  - `Ingested document id=doc_abc123 url=https://... chunks=17`
  - `Answered query id=qry_xyz789 retrieved=5 latency_ms=842`

## Error logging rules

- Log the exception where it is actually handled.
- If middleware or a transaction helper already logs the exception, do not log the same traceback again in the route.
- Include enough context to debug without exposing sensitive data.

## Batch discipline

- In early scaffolding batches, keep logging minimal — startup, shutdown, and `/health`.
- When DB arrives, add logs around DB lifecycle and successful inserts.
- When external service calls (LLM, embeddings) arrive, log call boundaries with latency, never request or response bodies.
- When auth arrives, log only auth outcomes, never auth secrets.
