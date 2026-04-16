"""Health check route."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Liveness probe — does not touch the database."""
    return {"data": {"status": "ok"}}
