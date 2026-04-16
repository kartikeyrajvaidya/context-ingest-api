"""Re-embed every chunk with the current OPENAI_EMBEDDING_MODEL.

One-shot operator CLI. Walks `chunks` in id-order via keyset pagination,
calls the embeddings API per batch, and bulk-writes the new vectors in
place. Never re-fetches source URLs, never re-chunks, never touches
`chunk_text`. Use after bumping `OPENAI_EMBEDDING_MODEL` to a
same-dimension model so retrieval quality doesn't silently drift.

Usage:
    python -m scripts.reembed_all [--batch-size N] [--dry-run]

Exit codes: 0 on success, 3 on any uncaught exception.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import traceback

from dotenv import load_dotenv

from configs.llm import LLMConfig
from core.services.embeddings import embed_texts
from db import db
from db.models.chunks import Chunk
from db.sqlalchemy.transaction import commit_transaction_async
from libs.logger import get_logger

logger = get_logger(__name__)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="reembed_all")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


async def _run(batch_size: int, dry_run: bool) -> None:
    model = LLMConfig.OPENAI_EMBEDDING_MODEL
    await db.connect()
    try:
        total = await Chunk.count_all()
        done = 0
        started = time.monotonic()

        async for batch in Chunk.iter_for_reembed(batch_size=batch_size):
            texts = [chunk_text for _, chunk_text in batch]
            new_embeddings = await embed_texts(texts)
            if not dry_run:
                async with commit_transaction_async():
                    await Chunk.update_embeddings_bulk(
                        [
                            (chunk_id, emb)
                            for (chunk_id, _), emb in zip(batch, new_embeddings)
                        ]
                    )
            done += len(batch)
            elapsed = time.monotonic() - started
            logger.info(
                "reembedded chunks=%d/%d elapsed_s=%.1f model=%s dry_run=%s",
                done, total, elapsed, model, dry_run,
            )

        elapsed = time.monotonic() - started
        summary = f"reembedded {done} chunks in {elapsed:.1f}s using {model}"
        if dry_run:
            summary += " (dry run — no writes)"
        sys.stdout.write(summary + "\n")
    finally:
        if db.session is not None:
            await db.session.remove()
        await db.disconnect()


def main() -> int:
    load_dotenv()
    args = _parse_args(sys.argv[1:])
    try:
        asyncio.run(_run(args.batch_size, args.dry_run))
        return 0
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
