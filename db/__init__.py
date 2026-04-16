"""Database package for ContextIngest API."""

from .connections.context_ingest_db import ContextIngestDB as db

__all__ = ["db"]
