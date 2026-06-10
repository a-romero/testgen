"""Test case generation templates (HLR1, HLR3, HLR7).

Templates bundle the Gym-style field variables, a Gherkin skeleton and a
versioned backend prompt template so generation behaviour is consistent and
controlled per project/platform.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from .. import storage
from ..models import Template, TemplateCreate

router = APIRouter()


# A ready-to-use starter template so the platform is usable immediately and
# demonstrates the BDD login example from the brief.
STARTER_TEMPLATE = {
    "name": "BDD Login (starter)",
    "description": "Example template generating BDD login scenarios.",
    "gherkin_template": (
        "Scenario: {scenario_title}\n"
        "  Given the user is on the login page\n"
        "  When the user enters {credential_type} credentials and clicks submit\n"
        "  Then the user should {expected_outcome}"
    ),
    "prompt_template": (
        "You are an Enterprise QA engineer. Using the requirements context and the "
        "provided variable values, write one concrete, unambiguous BDD login "
        "scenario in Gherkin Given/When/Then form."
    ),
    "fields": [
        {
            "name": "credential_type",
            "field_type": "enum",
            "description": "Type of credentials entered",
            "sample_values": ["valid", "invalid", "expired", "locked-out"],
        },
        {
            "name": "expected_outcome",
            "field_type": "expression",
            "description": "Outcome derived from credential type",
            "expression": (
                "'be redirected to the dashboard' if credential_type == 'valid' "
                "else 'see an authentication error message'"
            ),
            "depends_on": ["credential_type"],
        },
    ],
    "test_phase": "system",
    "test_techniques": ["positive", "negative", "boundary"],
    "output_detail": "standard",
}


@router.post("", response_model=Template)
def create_template(payload: TemplateCreate) -> Template:
    if payload.project_id and not storage.projects.get(payload.project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    template_id = f"tpl_{uuid.uuid4().hex[:10]}"
    record = payload.model_dump()
    record["version"] = 1
    saved = storage.templates.put(template_id, record)
    return Template(**saved)


@router.get("", response_model=list[Template])
def list_templates(project_id: str | None = None, include_global: bool = True) -> list[Template]:
    templates = storage.templates.list()
    if project_id:
        templates = [
            t
            for t in templates
            if t.get("project_id") == project_id or (include_global and not t.get("project_id"))
        ]
    return [Template(**t) for t in templates]


@router.get("/starter", response_model=TemplateCreate)
def get_starter_template() -> TemplateCreate:
    """Return a ready-made template definition the UI can pre-fill."""
    return TemplateCreate(**STARTER_TEMPLATE)


@router.get("/{template_id}", response_model=Template)
def get_template(template_id: str) -> Template:
    record = storage.templates.get(template_id)
    if not record:
        raise HTTPException(status_code=404, detail="Template not found")
    return Template(**record)


@router.put("/{template_id}", response_model=Template)
def update_template(template_id: str, payload: TemplateCreate) -> Template:
    """Update a template, bumping its version (controlled change — HLR7)."""
    existing = storage.templates.get(template_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    record = payload.model_dump()
    record["version"] = existing.get("version", 1) + 1
    saved = storage.templates.put(template_id, record)
    return Template(**saved)


@router.delete("/{template_id}")
def delete_template(template_id: str) -> dict:
    if not storage.templates.delete(template_id):
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": True, "id": template_id}
