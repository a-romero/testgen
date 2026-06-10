"""TestGen API — Enterprise QA test case generation platform.

A FastAPI service that turns requirements/context documents into unique BDD test
cases on a per-project basis, with reusable templates, human annotation and an
approval workflow.
"""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .deps import require_api_key
from .llm import LLMClient
from .routers import dashboard, documents, projects, templates, testcases

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="TestGen API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(require_api_key)]
app.include_router(projects.router, prefix="/projects", tags=["projects"], dependencies=_auth)
app.include_router(documents.router, prefix="/documents", tags=["documents"], dependencies=_auth)
app.include_router(templates.router, prefix="/templates", tags=["templates"], dependencies=_auth)
app.include_router(testcases.router, prefix="/testcases", tags=["testcases"], dependencies=_auth)
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=_auth)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "llm_available": LLMClient().available}


@app.get("/")
def root() -> dict:
    return {
        "name": "TestGen API",
        "version": "0.1.0",
        "description": "Enterprise QA test case generation platform",
        "llm_available": LLMClient().available,
        "endpoints": {
            "projects": "/projects",
            "documents": "/documents",
            "templates": "/templates",
            "testcases": "/testcases",
            "dashboard": "/dashboard",
            "docs": "/docs",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
