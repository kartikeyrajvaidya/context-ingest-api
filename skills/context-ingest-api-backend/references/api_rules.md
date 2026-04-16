# API Rules

## Design principles

- Contract first.
- Route thin, action thick.
- One resource, one router file.
- Keep request and response shapes explicit.
- Return only what the contract allows.

## Contract workflow

Before implementing a new endpoint:

1. Update or create the contract doc under `docs/api/`.
2. Confirm path, method, request body, response body, and error shape.
3. Only then scaffold route, schema, and action files.

## File placement

For a new resource or endpoint, follow this placement:

- `api/routes/<resource>.py`
- `core/schema/<resource>.py`
- `core/actions/<operation>.py`
- `db/models/<resource>.py` only when the active batch needs persistence

Keep `api/server/run_api.py` responsible for app boot and router registration only.

For deterministic helper code:

- prefer `core/utils/` over `core/tools/`
- keep DB-access helper methods on the model class for that table
- do not put SQL fetch logic in route files or generic utils when it belongs to one concrete model

## Request shape

Use the wrapped envelope:

```json
{
  "data": {
    "...": "..."
  }
}
```

Until a clear need appears, accept the top-level payload as a dict and validate `payload["data"]` with a schema class. Do not invent a generic wrapper abstraction early.

If multiple endpoints need the same wrapped-payload validation, use a small shared helper instead of duplicating route-local validation code.

## Response shape

- Return `{"data": ...}` for business responses.
- Return only the fields the contract specifies. Do not leak internal IDs, classifier labels, or debug fields.
- Do not add `count`, `meta`, `status`, or debug fields unless the contract explicitly requires them.

## Route rules

- Keep the route as small as possible.
- Route complexity should stay minimal — envelope parse, dependency wiring, action call, response shape. That's it.
- It is acceptable for the route to accept a raw wrapped payload and call a shared validation helper before invoking the action.
- Read principal or request state in the route only when auth exists.
- Delegate business work to an action.
- Keep only lightweight contract mapping and dependency wiring in the route.
- Keep business rules and persistence logic out of the route body.
- Do not accumulate helper functions or complex validation branches inside route files.

## Action rules

- Name actions by operation, not by generic layer names.
- Actions should absorb business and persistence complexity.
- Actions should do the real work and return a domain object or plain result that the route can shape into the contract.
- Actions may log meaningful business events once.
- Do not duplicate the same success log in both route and action.

## Model access rules

- If a function fetches rows for one concrete table, put that function on that table's model class.
- Keep model fetch helpers narrow and resource-specific.
- Deterministic transformation of already-fetched rows may live in `core/utils/`.

## Error handling

- Prefer shared assertions, `HTTPException`, and centralized exception handlers.
- Do not return ad-hoc error JSON from each route.
- Validation errors should be clear and field-specific.

## Adding a new API

Use this sequence:

1. contract doc
2. schema
3. route
4. action
5. router registration
6. local validation
7. DB model and migration only if the active batch needs it
8. auth only if the active batch needs it
