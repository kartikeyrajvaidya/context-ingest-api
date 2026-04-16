"""Ingest one URL or one local file without touching data/sources.json.

Handy for ad-hoc testing. For the normal flow, list sources in the manifest
and run `python -m scripts.ingest_all`.

Usage:
    python -m scripts.ingest_one --url https://example.com/post [--title T]
    python -m scripts.ingest_one --file data/knowledge/note.md [--title T] [--source knowledge://note]

Exit codes: 0 on ingested/unchanged, 1 on failed, 2 on argparse / missing file,
3 on any uncaught exception.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

from core.actions.ingest_document import ingest_document
from core.ingestion.cleaner import clean_raw_text
from core.schema.ingest import IngestRequestSchema
from db import db

REPO_ROOT = Path(__file__).resolve().parents[1]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ingest_one")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="URL to fetch and ingest.")
    source.add_argument("--file", help="Local text or markdown file to ingest.")
    parser.add_argument("--title", help="Optional title override.")
    parser.add_argument(
        "--source",
        help="Stable identifier for --file mode (e.g. knowledge://note). "
        "Defaults to text://<sha16> when omitted.",
    )
    return parser.parse_args(argv)


def _build_request(args: argparse.Namespace) -> tuple[IngestRequestSchema, str]:
    if args.url:
        if args.source:
            raise ValueError("--source is not allowed with --url; the URL is the identifier")
        return IngestRequestSchema(url=args.url, title=args.title), args.url

    path = Path(args.file)
    if not path.is_absolute():
        path = (REPO_ROOT / args.file).resolve()
    if not path.exists():
        raise FileNotFoundError(f"file not found: {args.file}")
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise ValueError(f"file is empty: {args.file}")
    is_markdown = path.suffix.lower() in (".md", ".markdown")
    text = clean_raw_text(raw, is_markdown=is_markdown)
    request = IngestRequestSchema(text=text, title=args.title, source_url=args.source)
    display = args.source or f"file://{args.file}"
    return request, display


async def _run(request: IngestRequestSchema, display: str) -> int:
    await db.connect()
    try:
        response = await ingest_document(request)
    finally:
        await db.disconnect()

    document_id = response.document_id or "-"
    sys.stdout.write(
        f"{document_id} {response.status} chunks={response.chunks} {display}\n"
    )
    return 0 if response.status in ("ingested", "unchanged") else 1


def main() -> int:
    load_dotenv()
    args = _parse_args(sys.argv[1:])
    try:
        request, display = _build_request(args)
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    try:
        return asyncio.run(_run(request, display))
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
