---
name: context-ingest-api-backend
description: Use when planning, scaffolding, or extending the backend. Enforces strict FastAPI/Postgres backend rules, batch discipline, API contract flow, raw-SQL migration policy, and logging conventions.
---

# Backend Skill

## When To Use

Use this skill for any backend work, especially when touching:

- API scaffolding or FastAPI app boot
- routes, schemas, actions, dependencies, middleware
- Postgres models, migrations, or transaction handling
- logging, error handling, or health checks
- batch planning for the rollout

This skill is the implementation guardrail for the repo. It is not a generic Python backend skill.

For RAG pipeline work (ingestion, retrieval, prompts, answer composition), also read:

- `../context-ingest-rag-pipeline/SKILL.md`

## Non-Negotiables

- The stack is **FastAPI**, not Flask. Do not introduce Flask unless the user explicitly changes the architecture decision.
- Mirror the layering described in `../../ARCHITECTURE.md` — thin routes, action-thick business logic, central transaction dependency, raw SQL migrations.
- Build only what the current batch requires. Do not add future abstractions early.
- Keep the contract in sync with `../../docs/api/`.
- Keep rollout scope in sync with `../../docs/scaffolding-plan.md`.
- Use **Postgres-first** design. Do not introduce alternative datastores.
- Do not add Redis, background workers, or generic repository/service layers unless the current batch explicitly needs them.

## Workflow

1. Read `../../docs/scaffolding-plan.md` and identify the active batch.
2. Read only the reference files needed for the current task.
3. Implement the smallest change that satisfies the batch.
4. Validate the change locally at the level the batch requires.
5. Update plan or contract docs if the behavior or rules changed.

## Reference Map

- `references/phase_rules.md`
  Use for rollout boundaries and what must not be implemented early.

- `references/stack_rules.md`
  Use for framework, dependency, and architecture decisions.

- `references/api_rules.md`
  Use when adding or changing routes, schemas, actions, responses, or tests.

- `references/migration_rules.md`
  Use for any DB schema work or migration creation.

- `references/logging_rules.md`
  Use for application logs, error logs, and request-level logging.

- `references/layering_rules.md`
  Use when implementing app boot, transactions, migrations, or the thin-route/thick-action pattern. Encodes the exact layering this repo enforces.

## Working Style

- Keep routes thin. Put business logic in `core/actions/`.
- Prefer explicit names over generic helpers.
- Add files only when they materially support the current batch.
- When a batch does not include a layer, do not create code for that layer.
- If the user asks for something that conflicts with the plan, update the plan first or explicitly call out the change.

## Output Expectations

When using this skill, changes should produce:

- a narrow diff
- explicit contract compliance
- predictable file placement
- no speculative infrastructure
- logging that is useful without leaking secrets
