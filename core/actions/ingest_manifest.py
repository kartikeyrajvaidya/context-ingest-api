"""Manifest-driven ingestion action.

Reads data/sources.json, walks every entry, calls ingest_document() per entry.
Shared by both scripts/ingest_all.py and api/routes/ingest.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.actions.ingest_document import ingest_document
from core.ingestion.cleaner import clean_raw_text
from core.schema.ingest import IngestRequestSchema
from libs.logger import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "sources.json"


class IngestManifestError(Exception):
    """Raised when one or more manifest entries fail to ingest."""


def _load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"manifest not found at {MANIFEST_PATH}")
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        sources = json.load(f)
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest must be a non-empty JSON array")
    return sources


def _build_request(entry: dict) -> IngestRequestSchema:
    url = entry["url"]
    title = entry.get("title")
    file_rel = entry.get("file")

    if file_rel:
        path = (REPO_ROOT / file_rel).resolve()
        if not path.exists():
            raise FileNotFoundError(f"file not found: {file_rel}")
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            raise ValueError(f"file is empty: {file_rel}")
        is_markdown = path.suffix.lower() in (".md", ".markdown")
        text = clean_raw_text(raw, is_markdown=is_markdown)
        return IngestRequestSchema(text=text, title=title, source_url=url)

    return IngestRequestSchema(url=url, title=title)


async def ingest_manifest() -> dict[str, int]:
    """Run the full manifest ingestion. Returns tallies dict.

    Raises IngestManifestError if any entry fails.
    """
    sources = _load_manifest()
    logger.info("Ingesting %d sources from manifest", len(sources))

    tallies = {"ingested": 0, "unchanged": 0, "failed": 0}

    for entry in sources:
        url = entry.get("url", "?")
        try:
            request = _build_request(entry)
            response = await ingest_document(request)
            tallies[response.status] += 1
            logger.info(
                "Manifest entry url=%s status=%s document_id=%s chunks=%d",
                url,
                response.status,
                response.document_id,
                response.chunks,
            )
        except Exception:  # noqa: BLE001
            logger.error("Failed to ingest: %s", url, exc_info=True)
            tallies["failed"] += 1

    logger.info(
        "Manifest ingestion complete ingested=%d unchanged=%d failed=%d",
        tallies["ingested"],
        tallies["unchanged"],
        tallies["failed"],
    )

    if tallies["failed"] > 0:
        raise IngestManifestError(
            f"{tallies['failed']} of {len(sources)} entries failed"
        )

    return tallies
