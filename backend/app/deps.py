"""Shared FastAPI dependencies."""

from fastapi import Header, HTTPException

from .config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> bool:
    """Validate the shared API key sent as the ``X-API-Key`` header.

    Kept deliberately simple for an internal tool. The default dev key allows
    local use without configuration; set ``TESTGEN_API_KEY`` to lock it down.
    """
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True
