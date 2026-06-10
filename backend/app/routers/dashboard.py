"""Dashboards & governance views (HLR5, HLR6).

Surfaces input quality, generation volume/trends, response quality (annotation
ratings), approval/adoption metrics and a market/platform-filtered governance
view of generation outcomes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter

from .. import storage
from ..models import TestCaseStatus

router = APIRouter()


def _ratings(testcases: List[Dict[str, Any]]) -> List[int]:
    ratings = []
    for tc in testcases:
        for ann in tc.get("annotations", []):
            if ann.get("rating") is not None:
                ratings.append(ann["rating"])
    return ratings


@router.get("/summary")
def summary(project_id: str | None = None) -> Dict[str, Any]:
    """Overall platform / project KPIs (HLR5)."""
    cases = storage.testcases.list()
    docs = storage.documents.list()
    gens = storage.generations.list()
    if project_id:
        cases = [c for c in cases if c.get("project_id") == project_id]
        docs = [d for d in docs if d.get("project_id") == project_id]
        gens = [g for g in gens if g.get("project_id") == project_id]

    status_counts = Counter(c.get("status", "generated") for c in cases)
    approved = status_counts.get(TestCaseStatus.APPROVED.value, 0)
    annotated = sum(1 for c in cases if c.get("annotations"))
    ratings = _ratings(cases)
    total_requested = sum(g.get("requested", 0) for g in gens)
    total_produced = sum(g.get("produced", 0) for g in gens)

    return {
        "projects": len(storage.projects.list()),
        "documents": len(docs),
        "approved_documents": sum(1 for d in docs if d.get("status") == "approved"),
        "test_cases": len(cases),
        "status_breakdown": dict(status_counts),
        "approval_rate": round(approved / len(cases), 3) if cases else 0.0,
        "annotation_coverage": round(annotated / len(cases), 3) if cases else 0.0,
        "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        # Context completeness: how many cases trace back to a source document.
        "context_completeness": round(
            sum(1 for c in cases if c.get("document_ids")) / len(cases), 3
        )
        if cases
        else 0.0,
        # Generation efficiency: produced vs requested (dedup impact visible here).
        "generation_yield": round(total_produced / total_requested, 3)
        if total_requested
        else None,
        "generation_runs": len(gens),
    }


@router.get("/trends")
def trends(project_id: str | None = None) -> Dict[str, Any]:
    """Generation volume over time (HLR5 generation trends)."""
    gens = storage.generations.list()
    if project_id:
        gens = [g for g in gens if g.get("project_id") == project_id]
    by_day: Dict[str, int] = defaultdict(int)
    for g in gens:
        day = (g.get("timestamp") or "")[:10]
        if day:
            by_day[day] += g.get("produced", 0)
    series = [{"date": d, "produced": n} for d, n in sorted(by_day.items())]
    return {"series": series}


@router.get("/governance")
def governance() -> Dict[str, Any]:
    """Filtered view of generation outcomes by market and platform (HLR6)."""
    cases = storage.testcases.list()
    projects = {p["id"]: p for p in storage.projects.list()}

    grid: Dict[str, Dict[str, Any]] = {}
    for tc in cases:
        project = projects.get(tc.get("project_id"), {})
        market = tc.get("market") or project.get("market") or "unspecified"
        platform = tc.get("platform") or project.get("platform") or "unspecified"
        key = f"{market} / {platform}"
        bucket = grid.setdefault(
            key,
            {"market": market, "platform": platform, "total": 0, "approved": 0, "rejected": 0},
        )
        bucket["total"] += 1
        if tc.get("status") == TestCaseStatus.APPROVED.value:
            bucket["approved"] += 1
        elif tc.get("status") == TestCaseStatus.REJECTED.value:
            bucket["rejected"] += 1

    rows = []
    for bucket in grid.values():
        bucket["approval_rate"] = (
            round(bucket["approved"] / bucket["total"], 3) if bucket["total"] else 0.0
        )
        rows.append(bucket)
    rows.sort(key=lambda r: r["total"], reverse=True)
    return {"rows": rows}
