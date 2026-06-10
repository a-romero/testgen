"""Export generated test cases to external formats/tools (HLR4).

Supported targets:
    * json     — full fidelity
    * csv      — generic spreadsheet
    * gherkin  — a ``.feature`` file
    * jira     — CSV shaped for Jira/Azure DevOps import (configurable mapping)
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional

# Default column mapping for Jira/ADO style imports. Callers may override any
# subset to align with their instance's field names (HLR4 configurable mappings).
DEFAULT_JIRA_MAPPING: Dict[str, str] = {
    "title": "Summary",
    "gherkin": "Description",
    "priority": "Priority",
    "test_phase": "Test Phase",
    "status": "Status",
    "tags": "Labels",
}


def to_json(testcases: List[Dict[str, Any]]) -> str:
    return json.dumps(testcases, indent=2, default=str)


def to_csv(testcases: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    cols = ["id", "title", "gherkin", "test_phase", "priority", "status", "market", "platform", "tags"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for tc in testcases:
        row = dict(tc)
        row["tags"] = ", ".join(tc.get("tags", []))
        writer.writerow(row)
    return buf.getvalue()


def to_gherkin(testcases: List[Dict[str, Any]], feature_name: str = "Generated test cases") -> str:
    lines = [f"Feature: {feature_name}", ""]
    for tc in testcases:
        for tag in tc.get("tags", []):
            lines.append(f"  @{tag}")
        gherkin = tc.get("gherkin") or ""
        for line in gherkin.splitlines():
            lines.append("  " + line if line.strip() else line)
        lines.append("")
    return "\n".join(lines)


def to_jira_csv(
    testcases: List[Dict[str, Any]], mapping: Optional[Dict[str, str]] = None
) -> str:
    mapping = {**DEFAULT_JIRA_MAPPING, **(mapping or {})}
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(list(mapping.values()))
    for tc in testcases:
        row = []
        for source in mapping.keys():
            value = tc.get(source, "")
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            row.append(value)
        writer.writerow(row)
    return buf.getvalue()


def export(
    testcases: List[Dict[str, Any]],
    fmt: str,
    feature_name: str = "Generated test cases",
    mapping: Optional[Dict[str, str]] = None,
) -> tuple[str, str, str]:
    """Return ``(content, media_type, filename)`` for the requested format."""
    fmt = (fmt or "json").lower()
    if fmt == "json":
        return to_json(testcases), "application/json", "testcases.json"
    if fmt == "csv":
        return to_csv(testcases), "text/csv", "testcases.csv"
    if fmt in ("gherkin", "feature"):
        return to_gherkin(testcases, feature_name), "text/plain", "testcases.feature"
    if fmt in ("jira", "ado"):
        return to_jira_csv(testcases, mapping), "text/csv", "testcases-jira.csv"
    raise ValueError(f"Unsupported export format: {fmt}")
