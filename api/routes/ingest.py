"""POST /v1/ingest — trigger manifest-driven ingestion."""

from fastapi import APIRouter

from core.actions.ingest_manifest import ingest_manifest

router = APIRouter()


@router.post("")
async def post_ingest() -> dict:
    await ingest_manifest()
    return {"data": {"ok": True}}
