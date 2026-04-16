"""HTTP fetcher for URL ingestion.

Knows about HTTP — not HTML parsing, chunking, or the database. Wraps
`httpx.AsyncClient` with explicit timeouts, a body-size cap, and a custom
User-Agent. Errors are wrapped in `FetchError` so the action layer has a
single non-fatal failure type to catch.
"""

from dataclasses import dataclass

import httpx

_USER_AGENT = "ContextIngest/0.1 (+https://github.com/kartikeyrajvaidya/context-ingest-api)"
_MAX_BODY_BYTES = 10_000_000
_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)


class FetchError(Exception):
    """Non-fatal fetch failure: HTTP error, timeout, DNS, TLS, or body too large."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    html: str


async def fetch_url(url: str) -> FetchedPage:
    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise FetchError(f"fetch {url}: HTTP {exc.response.status_code}") from exc
    except httpx.TimeoutException as exc:
        raise FetchError(f"fetch {url}: timeout") from exc
    except httpx.RequestError as exc:
        raise FetchError(f"fetch {url}: {exc}") from exc

    if len(response.content) > _MAX_BODY_BYTES:
        raise FetchError(f"fetch {url}: response body too large")

    return FetchedPage(url=str(response.url), html=response.text)
