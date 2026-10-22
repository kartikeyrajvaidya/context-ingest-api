# Phase Rules

Source of truth: `../../../docs/scaffolding-plan.md`

The plan document is canonical. If this file and the plan disagree, the plan wins. Update the plan first, then update this file.

## Hard boundaries

- Do not pull future-batch work into earlier batches.
- Do not add layers, files, or modules just because they may be useful later.
- Do not add abstractions before the second concrete use case appears. The first instance is hardcoded; the second instance is when you generalize.
- Do not add auth before the auth batch.
- Do not add background workers, queues, caches, or alternative datastores ever — these are not on the roadmap.
- Do not add streaming responses, conversation memory, or multi-tenancy — these are deliberate non-goals listed in `scaffolding-plan.md`.

## Batch identification

Before starting any work:

1. Read `../../../docs/scaffolding-plan.md`.
2. Identify which batch is currently active (marked with `⏳ next` or in-progress).
3. Read the acceptance criteria for that batch.
4. Implement the smallest change that satisfies one acceptance criterion.
5. Stop. Do not continue into the next batch's work without an explicit instruction.

## Batch type guidance

The plan describes batches by intent. Use these heuristics when interpreting an active batch:

- **Skeleton batches** — directory structure, meta files, CI, hygiene. No functional code. The acceptance test is "the next batch can start cleanly."
- **Boot batches** — the API boots and `/health` returns 200. Other routes exist as stubs that return `501`. DB exists with the full schema, even though most tables are empty.
- **Functionality batches** — one feature at a time. Real implementation behind one stub. Other stubs stay stubs until their batch.
- **Hardening batches** — observability, tests, docs, performance. No new features.

If the active batch is not one of these, ask the user to classify it before writing code.

## What "smallest change" means

- The smallest change is the one that satisfies the active acceptance criterion and nothing else.
- A bug fix touches the file with the bug and the test that exercises it. Not the surrounding code.
- A new endpoint touches one route, one schema, one action, optionally one model and migration. Not the existing endpoints.
- A refactor that "would be nice while we're here" is a separate batch. Open a discussion first.

## When the plan is wrong

Plans get out of sync. If you discover during implementation that the plan is missing a step or has a step in the wrong order:

1. Stop coding.
2. Update the plan to reflect what the code actually needs.
3. Confirm the change with the user.
4. Resume.

Do not silently work around a plan defect. The plan is the project's working memory, and silent workarounds are how the memory rots.
