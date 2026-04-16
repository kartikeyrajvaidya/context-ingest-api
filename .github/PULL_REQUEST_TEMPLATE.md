<!--
Thank you for contributing to ContextIngest API!

Before opening this PR, please make sure you have read CONTRIBUTING.md.
Small, focused PRs are merged fastest.
-->

## Summary

<!-- One or two sentences: what does this PR do and why? -->

## Type of change

<!-- Tick all that apply. Delete the rest. -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would change existing behavior)
- [ ] Documentation update
- [ ] Refactor (no behavior change)
- [ ] Build / CI / tooling

## Related issues

<!-- e.g. "Closes #42", "Refs #17". Leave blank if none. -->

## How was this tested?

<!--
At minimum, walk through the manual verification you ran. Examples:
- Restarted the API and hit /health
- Ingested https://example.com/post and confirmed N chunks in `chunks` table
- Ran POST /v1/query with "..." and verified the citations point at the right chunks
- Reran ingest on the same URL and confirmed status: "unchanged"

If you added or changed a contract, paste the before/after curl.
-->

## Checklist

- [ ] My code follows the layering rules in `ARCHITECTURE.md` (routes don't call services, actions own transactions)
- [ ] I ran `pre-commit run --all-files` locally and it passed
- [ ] I updated `docs/` for any contract or behavior change
- [ ] I updated `CHANGELOG.md` under `[Unreleased]`
- [ ] I added or updated migrations in **both** `db/migrations/versions/` and `db/migrations/sql/`
- [ ] I have not added new dependencies — or, if I did, I explained why above

## Screenshots / output

<!-- Optional. Helpful for UI-adjacent or curl-output changes. -->
