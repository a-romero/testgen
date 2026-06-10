"""Test case lifecycle: generate, review, annotate, approve, regenerate, export.

Covers HLR3 (generation), HLR4 (export/integrate), HLR9 (feedback &
regeneration), HLR10 (approval workflow) and HLR11 (capture feedback). Per the
brief, generated cases are guaranteed unique within a project (no duplicates).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .. import export as export_mod
from .. import storage
from ..generation import (
    BddSynthesizer,
    FieldGenerator,
    build_context,
    content_hash,
    generate_test_cases,
    render_gherkin,
)
from ..llm import LLMClient
from ..models import (
    Annotation,
    AnnotationCreate,
    ApprovalRequest,
    BddStep,
    DocumentStatus,
    GenerateRequest,
    RegenerateRequest,
    Template,
    TestCase,
    TestCaseStatus,
)

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_hashes(project_id: str) -> set[str]:
    return {
        tc.get("content_hash", "")
        for tc in storage.testcases.find(project_id=project_id)
        if tc.get("content_hash")
    }


@router.post("/generate", response_model=list[TestCase])
def generate(req: GenerateRequest) -> list[TestCase]:
    project = storage.projects.get(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    template_record = storage.templates.get(req.template_id)
    if not template_record:
        raise HTTPException(status_code=404, detail="Template not found")
    template = Template(**template_record)

    # Resolve the source documents (HLR2 collation; HLR10 approval gating).
    docs = []
    for doc_id in req.document_ids:
        doc = storage.documents.get(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        if req.require_approved_documents and doc.get("status") != DocumentStatus.APPROVED.value:
            raise HTTPException(
                status_code=400,
                detail=f"Document {doc_id} is not approved; required for generation",
            )
        docs.append(doc)

    llm = LLMClient(model=req.llm_model)
    cases = generate_test_cases(
        template=template,
        documents=docs,
        project=project,
        num_cases=req.num_cases,
        existing_hashes=_existing_hashes(req.project_id),
        llm=llm,
        extra_instructions=req.extra_instructions,
        document_ids=req.document_ids,
    )

    for tc in cases:
        storage.testcases.put(tc.id, tc.model_dump(mode="json"))

    # Record the generation run for trend dashboards (HLR5).
    storage.generations.put(
        f"gen_{uuid.uuid4().hex[:10]}",
        {
            "project_id": req.project_id,
            "template_id": req.template_id,
            "document_ids": req.document_ids,
            "requested": req.num_cases,
            "produced": len(cases),
            "generator": "llm" if llm.available else "template",
            "timestamp": _now(),
        },
    )
    return cases


@router.get("", response_model=list[TestCase])
def list_testcases(
    project_id: str | None = None,
    status: str | None = None,
    market: str | None = None,
    platform: str | None = None,
) -> list[TestCase]:
    cases = storage.testcases.list()
    if project_id:
        cases = [c for c in cases if c.get("project_id") == project_id]
    if status:
        cases = [c for c in cases if c.get("status") == status]
    if market:
        cases = [c for c in cases if c.get("market") == market]
    if platform:
        cases = [c for c in cases if c.get("platform") == platform]
    return [TestCase(**c) for c in cases]


@router.get("/{testcase_id}", response_model=TestCase)
def get_testcase(testcase_id: str) -> TestCase:
    record = storage.testcases.get(testcase_id)
    if not record:
        raise HTTPException(status_code=404, detail="Test case not found")
    return TestCase(**record)


@router.delete("/{testcase_id}")
def delete_testcase(testcase_id: str) -> dict:
    if not storage.testcases.delete(testcase_id):
        raise HTTPException(status_code=404, detail="Test case not found")
    return {"deleted": True, "id": testcase_id}


# --------------------------------------------------------------------------- #
# Human annotation & approval (HLR10, HLR11)
# --------------------------------------------------------------------------- #
@router.post("/{testcase_id}/annotations", response_model=TestCase)
def add_annotation(testcase_id: str, payload: AnnotationCreate) -> TestCase:
    record = storage.testcases.get(testcase_id)
    if not record:
        raise HTTPException(status_code=404, detail="Test case not found")
    annotation = Annotation(
        id=f"ann_{uuid.uuid4().hex[:8]}",
        author=payload.author,
        verdict=payload.verdict,
        comment=payload.comment,
        rating=payload.rating,
        created_at=_now(),
    )
    record.setdefault("annotations", []).append(annotation.model_dump(mode="json"))
    # Reflect the latest human verdict in the test case status.
    if payload.verdict.value == "needs_changes":
        record["status"] = TestCaseStatus.NEEDS_CHANGES.value
    elif record.get("status") == TestCaseStatus.GENERATED.value:
        record["status"] = TestCaseStatus.PENDING_REVIEW.value
    saved = storage.testcases.put(testcase_id, record)
    return TestCase(**saved)


@router.post("/{testcase_id}/approve", response_model=TestCase)
def approve_testcase(testcase_id: str, payload: ApprovalRequest) -> TestCase:
    record = storage.testcases.get(testcase_id)
    if not record:
        raise HTTPException(status_code=404, detail="Test case not found")
    if payload.approve:
        record["status"] = TestCaseStatus.APPROVED.value
        record["approved_by"] = payload.approved_by
        record["approved_at"] = _now()
    else:
        record["status"] = TestCaseStatus.REJECTED.value
        record["approved_by"] = payload.approved_by
        record["approved_at"] = _now()
    if payload.comment:
        record.setdefault("annotations", []).append(
            Annotation(
                id=f"ann_{uuid.uuid4().hex[:8]}",
                author=payload.approved_by,
                verdict="valid" if payload.approve else "invalid",
                comment=payload.comment,
                created_at=_now(),
            ).model_dump(mode="json")
        )
    saved = storage.testcases.put(testcase_id, record)
    return TestCase(**saved)


# --------------------------------------------------------------------------- #
# Multi-round feedback-driven regeneration (HLR9)
# --------------------------------------------------------------------------- #
@router.post("/{testcase_id}/regenerate", response_model=TestCase)
def regenerate(testcase_id: str, payload: RegenerateRequest) -> TestCase:
    record = storage.testcases.get(testcase_id)
    if not record:
        raise HTTPException(status_code=404, detail="Test case not found")
    template_record = storage.templates.get(record.get("template_id"))
    if not template_record:
        raise HTTPException(status_code=400, detail="Originating template no longer exists")
    template = Template(**template_record)

    docs = [storage.documents.get(d) for d in record.get("document_ids", [])]
    docs = [d for d in docs if d]
    context = build_context(docs)

    llm = LLMClient(model=payload.llm_model)
    synth = BddSynthesizer(llm=llm)
    # Reuse the original field values so the revision stays on-scenario.
    fields = record.get("fields", {})
    scenario = synth.synthesize(
        template, fields, context, feedback=payload.feedback
    )

    # Preserve the prior version in the regeneration history (HLR9).
    record.setdefault("regeneration_history", []).append(
        {
            "title": record.get("title"),
            "gherkin": record.get("gherkin"),
            "feedback": payload.feedback,
            "author": payload.author,
            "timestamp": _now(),
        }
    )
    steps = [{"keyword": s["keyword"], "text": s["text"]} for s in scenario["steps"]]
    record["title"] = scenario["title"]
    record["steps"] = steps
    record["gherkin"] = render_gherkin(scenario["title"], steps)
    record["priority"] = scenario.get("priority", record.get("priority", "medium"))
    record["content_hash"] = content_hash(scenario["title"], steps)
    record["status"] = TestCaseStatus.PENDING_REVIEW.value
    saved = storage.testcases.put(testcase_id, record)
    return TestCase(**saved)


# --------------------------------------------------------------------------- #
# Export / integrate (HLR4)
# --------------------------------------------------------------------------- #
@router.get("/export/{project_id}")
def export_testcases(
    project_id: str,
    format: str = "json",
    status: str | None = None,
    approved_only: bool = False,
) -> Response:
    project = storage.projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    cases = storage.testcases.find(project_id=project_id)
    if approved_only:
        cases = [c for c in cases if c.get("status") == TestCaseStatus.APPROVED.value]
    elif status:
        cases = [c for c in cases if c.get("status") == status]
    try:
        content, media_type, filename = export_mod.export(
            cases, format, feature_name=project.get("name", "Generated test cases")
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
