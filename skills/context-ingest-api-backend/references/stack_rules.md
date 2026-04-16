# Stack Rules

## Locked decisions

- Language/runtime: Python 3.11
- API framework: FastAPI
- ASGI server: Uvicorn
- DB: Postgres (with pgvector extension)
- ORM/session layer: SQLAlchemy async
- Migration runner: Alembic wrappers that execute raw SQL files
- Container/dev flow: Docker Compose when local infra is needed

## What not to introduce by default

- Flask
- Redis
- Celery or background workers
- generic repository layers
- generic service registries
- event buses
- caching layers
- alternative vector stores (Pinecone, Weaviate, Qdrant)

## Layering rule

The repo enforces a strict layering:

- thin routes — request envelope parsing + dependency wiring only
- action-oriented business logic in `core/actions/`
- middleware-based request processing
- central transaction dependency shared across actions
- simple logger wrapper in `libs/logger.py`
- raw SQL migrations executed by Alembic wrappers

Do not introduce these unless the active batch explicitly needs them:

- multi-tenant data model
- JWT or auth-provider integration
- file upload pipelines
- broad CRUD surface area
- view-heavy schema design
