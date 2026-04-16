# Security Policy

The ContextIngest API maintainers take security seriously. This document explains how to report vulnerabilities, what we consider in scope, and what you can expect from us in response.

## Supported versions

ContextIngest API is in **alpha** (`0.x`). Until `1.0.0`, only the latest tagged release receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| `0.x` (latest) | ✅ |
| Older `0.x`    | ❌ |

Once `1.0.0` ships, this table will be updated to reflect a stable support window.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.** Public reports give attackers a head start before a fix is available.

Instead, email:

**kartikeyrajvaidya@gmail.com**

with the subject line `[context-ingest-api security] <short summary>`.

Please include, where possible:

- A description of the issue and its impact
- Steps to reproduce, or a proof-of-concept
- The affected version, commit, or branch
- Any suggested mitigation
- Whether you'd like credit in the eventual advisory

If you prefer encrypted communication, ask in your initial email and we will exchange a key.

## What you can expect

| Stage | Target |
|-------|--------|
| Acknowledgement of report | within **3 business days** |
| Initial assessment (severity, in-scope?) | within **7 business days** |
| Fix or mitigation in `main` | within **30 days** for high/critical, **90 days** for low/medium |
| Public disclosure (advisory + release) | coordinated with reporter, default **90 days** after report |

We will keep you updated as the investigation progresses, even if there is no new information.

## Scope

**In scope:**

- The ContextIngest API codebase in this repository
- Default Docker images built from this repository
- The default `docker-compose.yaml` deployment topology
- Documentation that, if followed, would lead a user into an insecure configuration

**Out of scope:**

- Vulnerabilities in upstream dependencies (FastAPI, SQLAlchemy, OpenAI SDK, Postgres, pgvector, trafilatura, etc.) — please report those to the respective projects. We will, however, bump the dependency promptly once a fixed version is available.
- Issues that require a malicious operator with database or filesystem access (ContextIngest trusts its own DB).
- Denial-of-service via expensive but legitimate ingestion or query payloads. Use rate limiting and a reverse proxy in production.
- Missing authentication on the v0 API. ContextIngest v0 is intentionally unauthenticated and is documented to require a reverse proxy or network-level access control if exposed publicly. See [`README.md`](./README.md) and [`docs/guides/self-hosting.md`](./docs/guides/self-hosting.md).

## Safe harbor

We will not pursue legal action against researchers who:

- Make a good-faith effort to comply with this policy
- Avoid privacy violations, data destruction, and service disruption
- Give us a reasonable window to investigate and remediate before public disclosure

Thank you for helping keep ContextIngest API and its users safe.
