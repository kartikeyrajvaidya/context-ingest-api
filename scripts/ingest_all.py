"""Ingest every source listed in data/sources.json.

CLI wrapper around ingest_manifest(). For HTTP access use POST /v1/ingest.

Usage:
    python -m scripts.ingest_all

Exit codes: 0 on success, 1 on partial failure, 3 on uncaught exception.
"""

from __future__ import annotations

import asyncio
import sys
import traceback

from dotenv import load_dotenv

from core.actions.ingest_manifest import IngestManifestError, ingest_manifest
from db import db
from libs.logger import get_logger

logger = get_logger(__name__)


async def _run() -> int:
    await db.connect()
    try:
        tallies = await ingest_manifest()
    except IngestManifestError:
        return 1
    finally:
        await db.disconnect()

    sys.stdout.write(
        f"ingested={tallies['ingested']} unchanged={tallies['unchanged']} "
        f"failed={tallies['failed']}\n"
    )
    return 0


def main() -> int:
    load_dotenv()
    try:
        return asyncio.run(_run())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
