"""Context / requirements documents (HLR1, HLR2, HLR10).

Supports collate, upload, version, approve, store and retrieve with market /
platform / project filtering and a lightweight approval workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import storage
from ..models import Document, DocumentCreate, DocumentStatus

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("", response_model=Document)
def create_document(payload: DocumentCreate) -> Document:
    if not storage.projects.get(payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    record = payload.model_dump()
    record.update(
        {
            "version": 1,
            "family_id": doc_id,           # first version seeds the family
            "status": DocumentStatus.DRAFT.value,
            "approved_by": None,
            "approved_at": None,
        }
    )
    saved = storage.documents.put(doc_id, record)
    return Document(**saved)


@router.post("/upload", response_model=Document)
async def upload_document(
    project_id: str = Form(...),
    title: str = Form(...),
    doc_type: str = Form("requirements"),
    market: str = Form(""),
    platform: str = Form(""),
    file: UploadFile = File(...),
) -> Document:
    """Upload a requirements document file (txt / md / csv decoded as UTF-8)."""
    if not storage.projects.get(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("latin-1", errors="replace")
    payload = DocumentCreate(
        project_id=project_id,
        title=title or file.filename or "Uploaded document",
        content=content,
        doc_type=doc_type,
        market=market,
        platform=platform,
        metadata={"filename": file.filename},
    )
    return create_document(payload)


@router.get("", response_model=list[Document])
def list_documents(
    project_id: str | None = None,
    market: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    latest_only: bool = False,
) -> list[Document]:
    docs = storage.documents.list()
    if project_id:
        docs = [d for d in docs if d.get("project_id") == project_id]
    if market:
        docs = [d for d in docs if d.get("market") == market]
    if platform:
        docs = [d for d in docs if d.get("platform") == platform]
    if status:
        docs = [d for d in docs if d.get("status") == status]
    if latest_only:
        # Keep only the highest version per family.
        by_family: dict[str, dict] = {}
        for d in docs:
            fam = d.get("family_id", d["id"])
            if fam not in by_family or d.get("version", 1) > by_family[fam].get("version", 1):
                by_family[fam] = d
        docs = list(by_family.values())
    return [Document(**d) for d in docs]


@router.get("/{document_id}", response_model=Document)
def get_document(document_id: str) -> Document:
    record = storage.documents.get(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    return Document(**record)


@router.get("/{document_id}/versions", response_model=list[Document])
def list_versions(document_id: str) -> list[Document]:
    record = storage.documents.get(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    family = record.get("family_id", document_id)
    versions = [d for d in storage.documents.list() if d.get("family_id") == family]
    versions.sort(key=lambda d: d.get("version", 1))
    return [Document(**d) for d in versions]


@router.post("/{document_id}/versions", response_model=Document)
def create_version(document_id: str, payload: DocumentCreate) -> Document:
    """Create a new version of an existing document, preserving its family."""
    base = storage.documents.get(document_id)
    if not base:
        raise HTTPException(status_code=404, detail="Document not found")
    family = base.get("family_id", document_id)
    versions = [d for d in storage.documents.list() if d.get("family_id") == family]
    next_version = max((d.get("version", 1) for d in versions), default=1) + 1
    new_id = f"doc_{uuid.uuid4().hex[:10]}"
    record = payload.model_dump()
    record.update(
        {
            "project_id": base["project_id"],
            "family_id": family,
            "version": next_version,
            "status": DocumentStatus.DRAFT.value,
            "approved_by": None,
            "approved_at": None,
        }
    )
    saved = storage.documents.put(new_id, record)
    return Document(**saved)


@router.post("/{document_id}/approve", response_model=Document)
def approve_document(document_id: str, approved_by: str = "qa-lead") -> Document:
    record = storage.documents.get(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    record["status"] = DocumentStatus.APPROVED.value
    record["approved_by"] = approved_by
    record["approved_at"] = _now()
    saved = storage.documents.put(document_id, record)
    return Document(**saved)


@router.post("/{document_id}/status", response_model=Document)
def set_status(document_id: str, status: DocumentStatus) -> Document:
    record = storage.documents.get(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    record["status"] = status.value
    saved = storage.documents.put(document_id, record)
    return Document(**saved)


@router.delete("/{document_id}")
def delete_document(document_id: str) -> dict:
    if not storage.documents.delete(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": document_id}
