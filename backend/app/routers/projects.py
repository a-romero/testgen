"""Project CRUD — the per-project unit of organisation for the QA team."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from .. import storage
from ..models import Project, ProjectCreate

router = APIRouter()


@router.post("", response_model=Project)
def create_project(payload: ProjectCreate) -> Project:
    project_id = f"prj_{uuid.uuid4().hex[:10]}"
    record = storage.projects.put(project_id, payload.model_dump())
    return Project(**record)


@router.get("", response_model=list[Project])
def list_projects() -> list[Project]:
    return [Project(**p) for p in storage.projects.list()]


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    record = storage.projects.get(project_id)
    if not record:
        raise HTTPException(status_code=404, detail="Project not found")
    return Project(**record)


@router.put("/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectCreate) -> Project:
    existing = storage.projects.get(project_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Project not found")
    existing.update(payload.model_dump())
    record = storage.projects.put(project_id, existing)
    return Project(**record)


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict:
    if not storage.projects.delete(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    # Cascade delete dependent records so the workspace stays consistent.
    for doc in storage.documents.find(project_id=project_id):
        storage.documents.delete(doc["id"])
    for tc in storage.testcases.find(project_id=project_id):
        storage.testcases.delete(tc["id"])
    for tpl in storage.templates.find(project_id=project_id):
        storage.templates.delete(tpl["id"])
    return {"deleted": True, "id": project_id}
