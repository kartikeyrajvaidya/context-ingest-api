"""Database package for ContextIngest API."""

from .connections.context_ingest_db import ContextIngestDB as db  # noqa: N813

__all__ = ["db"]
