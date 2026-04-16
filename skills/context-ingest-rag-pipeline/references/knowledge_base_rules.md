# Knowledge Base Document Rules

These rules govern the creation, editing, and verification of internal reference documents that are ingested into the retrieval index alongside or instead of fetched URLs.

## Purpose

Knowledge documents are the authoritative internal reference layer for the bot. They are chunked, embedded, and retrieved at query time. Every claim in these documents may be surfaced verbatim to users. Accuracy is non-negotiable.

## File format

- Plain markdown (`.md`)
- Filename: kebab-case matching the topic, e.g. `setup-instructions.md`
- First line: `# Title` heading
- No YAML frontmatter — metadata is supplied to the ingestion call
- Structure with `##` for major sections, `###` for subsections
- No images, no inline HTML, no embedded scripts (the cleaner strips them)
- Use the formatting conventions of the operator's domain (units, currency, date format) consistently

## Content principles

### Write for retrieval, not for reading

Each section should be self-contained enough that a single chunk makes sense on its own. A chunk that says "same as above" or "see previous section" is useless when retrieved in isolation.

- Lead each subsection with the key fact (number, threshold, identifier, decision)
- Include qualifying conditions inline, not in a separate "general rules" preamble
- Repeat shared context (e.g. "applies only when X is true") in each relevant subsection rather than stating it once at the top

### One topic per file

Each file covers one coherent topic. If a topic naturally splits into several closely-related sub-topics, keep them in the same file as separate sections. If two topics are only loosely related, use separate files.

### Be specific, not exhaustive

Include the information that answers real user questions. Skip obscure edge cases, historical trivia, and provisions that apply to a tiny minority of users. The goal is a reliable 80/20 reference, not a reproduction of the source spec.

## Accuracy rules

### The cardinal rule: if you are not sure, skip it

Do not include a claim unless you can point to a specific source — an official document, a primary source, a vendor specification, an authoritative URL. When in doubt:

- Omit the claim entirely, OR
- State what is known and explicitly mark the uncertain part: "This threshold may have changed in the latest release — verify before relying on this figure."

Never fill a gap with a plausible guess. A missing fact is recoverable. A wrong fact that gets embedded into the retrieval index and served to users is a trust-destroying bug.

### Verification before writing

For every numerical or otherwise verifiable claim:

1. Identify the source: which spec, which official documentation, which release note
2. Cross-check against at least one reliable source
3. If sources conflict, either use the most authoritative source or skip the claim

### Version awareness

- Always state which version, release, or effective date a fact applies to
- When a value changes between versions, state both and label them
- Never assume a release "probably" changed something — release changes are specific and documented

### Common error patterns to avoid

These are the patterns that most often produce wrong knowledge documents:

| Error pattern | Prevention |
|---|---|
| Confusing similar limits or identifiers | Always verify against the specific section of the source |
| Applying a rule to the wrong scope | Read the actual scope, not summaries |
| Using outdated values after a release | Always check the applicable version |
| Stating "only X" when "X and Y" | Verify the full scope of the rule |
| Assuming a recent change | Only state confirmed changes |

## Adding a new document

1. Write the document following all rules above.
2. Run a verification pass: for each verifiable claim, confirm the source.
3. Ingest it via the CLI — `python -m scripts.ingest_url --text-file <path> --source internal://<slug-matching-filename> --title "<title>"`. (There is no HTTP ingest route in v0.)

## Editing an existing document

1. Read the full document first.
2. Make the edit.
3. Verify the edit against a source — do not assume the correction is correct just because it sounds right.
4. Re-ingest via the same CLI command. The pipeline uses content hashing, so unchanged content is a no-op and changed content is fully re-chunked and re-embedded.

## Verification checklist for reviews

When reviewing a knowledge document (new or edited), check each claim against this list:

- [ ] The source is identified for every verifiable claim
- [ ] Numeric values are current for the stated version or release
- [ ] Scope and applicability are explicitly stated
- [ ] Version attribution is accurate (not assumed)
- [ ] Deadlines, thresholds, and conditions match the source spec
- [ ] No claim relies on a single unverified source or on "probably"
- [ ] The document reads sensibly when split into ~500-token chunks
