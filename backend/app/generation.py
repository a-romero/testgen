"""Test case generation engine.

Two cooperating pieces, inspired by the qstudio Gym's template-based data
designer:

1. ``FieldGenerator`` — produces a *row* of independent variables. Each field is
   generated according to its own type (enum, sampling, LLM, expression, date,
   number, boolean, string), respecting inter-field dependencies via a
   topological sort and tracking ``unique`` fields.

2. ``BddSynthesizer`` — turns the requirements context + a row of field values
   into a BDD (Given/When/Then) scenario, using an LLM when available and a
   deterministic template otherwise.

The orchestrator (``generate_test_cases``) guarantees **uniqueness within a
project** by hashing the normalised scenario and retrying until enough distinct
cases are produced (or attempts are exhausted).
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from .llm import LLMClient
from .models import (
    BddStep,
    Document,
    FieldDefinition,
    FieldType,
    Template,
    TestCase,
    TestCaseStatus,
)

logger = logging.getLogger("testgen.generation")

_STEP_RE = re.compile(r"^\s*(Given|When|Then|And|But)\b\s*(.*)$", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Field (variable) generation
# --------------------------------------------------------------------------- #
class FieldGenerator:
    def __init__(self, fields: List[FieldDefinition], llm: Optional[LLMClient] = None):
        self.fields = {f.name: f for f in fields}
        self.llm = llm
        # Track values already emitted for fields marked ``unique``.
        self._used: Dict[str, Set[str]] = {f.name: set() for f in fields}

    def _topo_order(self) -> List[str]:
        graph = {name: set(f.depends_on or []) for name, f in self.fields.items()}
        in_degree = {name: 0 for name in self.fields}
        for deps in graph.values():
            for dep in deps:
                if dep in in_degree:
                    in_degree[dep] += 1
        # Fields that nothing depends on should still be emitted; we order so
        # that dependencies are generated before their dependents.
        order: List[str] = []
        # Standard Kahn's algorithm where an edge dep -> node means dep first.
        rev: Dict[str, List[str]] = {n: [] for n in self.fields}
        indeg = {n: 0 for n in self.fields}
        for node, deps in graph.items():
            for dep in deps:
                if dep in rev:
                    rev[dep].append(node)
                    indeg[node] += 1
        queue = [n for n, d in indeg.items() if d == 0]
        while queue:
            node = queue.pop(0)
            order.append(node)
            for nxt in rev[node]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)
        for name in self.fields:  # append any cyclic remainder deterministically
            if name not in order:
                order.append(name)
        return order

    def generate_row(self, context: str = "") -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        for name in self._topo_order():
            field = self.fields[name]
            value = self._generate_value(field, row, context)
            # Best-effort uniqueness: resample a few times for unique fields.
            if field.unique:
                attempts = 0
                while str(value) in self._used[name] and attempts < 25:
                    value = self._generate_value(field, row, context)
                    attempts += 1
                self._used[name].add(str(value))
            row[name] = value
        return row

    def _generate_value(self, field: FieldDefinition, row: Dict[str, Any], context: str) -> Any:
        ftype = field.field_type
        if ftype in (FieldType.ENUM, FieldType.SAMPLING):
            return self._sample(field)
        if ftype == FieldType.LLM_GENERATED:
            return self._llm_value(field, row, context)
        if ftype == FieldType.EXPRESSION:
            return self._expression(field, row)
        if ftype == FieldType.DATE:
            return self._date(field)
        if ftype == FieldType.NUMBER:
            return self._number(field)
        if ftype == FieldType.BOOLEAN:
            return random.choice([True, False])
        if ftype == FieldType.STRING:
            return field.default if field.default is not None else field.description
        return None

    def _sample(self, field: FieldDefinition) -> Any:
        values = field.sample_values or []
        if not values:
            return None
        if field.weights and len(field.weights) == len(values):
            return random.choices(values, weights=field.weights, k=1)[0]
        return random.choice(values)

    def _llm_value(self, field: FieldDefinition, row: Dict[str, Any], context: str) -> str:
        if not (self.llm and self.llm.available):
            # Deterministic stand-in keeps generation working offline.
            seed = field.sample_values[0] if field.sample_values else field.description
            return f"{seed or field.name}-{uuid.uuid4().hex[:6]}"
        prompt = field.llm_prompt or f"Generate a realistic value for: {field.description or field.name}"
        if row:
            prompt += "\n\nAlready-generated field values:\n" + json.dumps(row, default=str)
        if context:
            prompt += f"\n\nRequirements context (excerpt):\n{context[:1500]}"
        prompt += "\n\nReturn ONLY the value, no preamble."
        try:
            return self.llm.complete(prompt, max_tokens=80).strip().strip('"')
        except Exception as exc:  # pragma: no cover
            logger.warning("LLM field generation failed for %s: %s", field.name, exc)
            return field.description or field.name

    def _expression(self, field: FieldDefinition, row: Dict[str, Any]) -> Any:
        if not field.expression:
            return None
        try:
            return eval(field.expression, {"__builtins__": {}}, dict(row))  # noqa: S307
        except Exception as exc:
            logger.warning("Expression failed for %s: %s", field.name, exc)
            return None

    def _date(self, field: FieldDefinition) -> str:
        def parse(val: Optional[str], default: datetime) -> datetime:
            if not val:
                return default
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                return default

        now = datetime.now(timezone.utc)
        lo = parse(field.date_min, now)
        hi = parse(field.date_max, now + timedelta(days=365))
        span = max((hi - lo).days, 1)
        result = lo + timedelta(days=random.randrange(span))
        return result.strftime(field.date_format) if field.date_format else result.date().isoformat()

    def _number(self, field: FieldDefinition):
        lo = field.number_min if field.number_min is not None else 0
        hi = field.number_max if field.number_max is not None else 100
        if field.number_type == "int":
            return random.randint(int(lo), int(hi))
        return round(random.uniform(lo, hi), 2)


# --------------------------------------------------------------------------- #
# BDD scenario synthesis
# --------------------------------------------------------------------------- #
class BddSynthesizer:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm

    def synthesize(
        self,
        template: Template,
        fields: Dict[str, Any],
        context: str,
        extra_instructions: str = "",
        feedback: str = "",
    ) -> Dict[str, Any]:
        """Return ``{"title": str, "steps": [{keyword,text}], "priority": str}``."""
        if self.llm and self.llm.available:
            result = self._llm_synthesize(template, fields, context, extra_instructions, feedback)
            if result:
                return result
        return self._template_synthesize(template, fields)

    def _llm_synthesize(
        self,
        template: Template,
        fields: Dict[str, Any],
        context: str,
        extra_instructions: str,
        feedback: str,
    ) -> Optional[Dict[str, Any]]:
        techniques = ", ".join(template.test_techniques) or "happy path and negative cases"
        instruction = template.prompt_template or (
            "Write a single concrete BDD scenario in Gherkin Given/When/Then form."
        )
        detail = {
            "high_level": "Keep it to a one-line Given/When/Then.",
            "standard": "Use clear Given/When/Then steps, adding And/But where natural.",
            "detailed": "Use Given/When/Then plus And/But steps and reference concrete test data.",
        }.get(getattr(template.output_detail, "value", str(template.output_detail)), "")

        prompt = f"""{instruction}

Test phase: {getattr(template.test_phase, 'value', template.test_phase)}
Test techniques to apply: {techniques}
Output detail: {detail}

Requirements / acceptance criteria context:
\"\"\"
{context[:4000]}
\"\"\"

Use these specific variable values in the scenario (do not invent contradicting values):
{json.dumps(fields, indent=2, default=str)}
"""
        if extra_instructions:
            prompt += f"\nAdditional instructions: {extra_instructions}\n"
        if feedback:
            prompt += f"\nRevise according to this reviewer feedback: {feedback}\n"
        prompt += """
Respond ONLY with JSON of the form:
{
  "title": "Short scenario title",
  "priority": "high|medium|low",
  "steps": [
    {"keyword": "Given", "text": "..."},
    {"keyword": "When", "text": "..."},
    {"keyword": "Then", "text": "..."}
  ]
}"""
        data = self.llm.complete_json(prompt)
        if not data or "steps" not in data:
            return None
        steps = [
            {"keyword": str(s.get("keyword", "And")).title(), "text": str(s.get("text", "")).strip()}
            for s in data.get("steps", [])
            if s.get("text")
        ]
        if not steps:
            return None
        return {
            "title": str(data.get("title") or "Generated scenario").strip(),
            "priority": str(data.get("priority", "medium")).lower(),
            "steps": steps,
        }

    def _template_synthesize(self, template: Template, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic fallback: fill the Gherkin template with field values."""
        safe = _SafeDict(fields)
        rendered = template.gherkin_template.format_map(safe)
        steps: List[Dict[str, str]] = []
        title = "Generated scenario"
        for line in rendered.splitlines():
            line = line.strip()
            if line.lower().startswith("scenario:"):
                parsed = line.split(":", 1)[1].strip()
                # Ignore an unresolved ``{scenario_title}`` placeholder — the
                # template author expects the generator to supply the title.
                if parsed and "{" not in parsed:
                    title = parsed
                continue
            match = _STEP_RE.match(line)
            if match:
                steps.append({"keyword": match.group(1).title(), "text": match.group(2).strip()})
        if not steps:
            # Construct a minimal scenario purely from field values.
            joined = ", ".join(f"{k}={v}" for k, v in fields.items())
            steps = [
                {"keyword": "Given", "text": f"the system is in a known state with {joined or 'default data'}"},
                {"keyword": "When", "text": "the user performs the action under test"},
                {"keyword": "Then", "text": "the expected outcome is observed"},
            ]
        # Make the title unique-ish from the field values so two rows differ.
        descriptor = " / ".join(str(v) for v in list(fields.values())[:2])
        if descriptor:
            title = f"{title} [{descriptor}]"
        return {"title": title, "priority": "medium", "steps": steps}


class _SafeDict(dict):
    """``str.format_map`` helper that leaves unknown placeholders untouched."""

    def __missing__(self, key: str) -> str:  # pragma: no cover - trivial
        return "{" + key + "}"


# --------------------------------------------------------------------------- #
# Rendering, hashing & orchestration
# --------------------------------------------------------------------------- #
def render_gherkin(title: str, steps: List[Dict[str, str]]) -> str:
    lines = [f"Scenario: {title}"]
    for step in steps:
        lines.append(f"  {step['keyword']} {step['text']}")
    return "\n".join(lines)


def content_hash(title: str, steps: List[Dict[str, str]]) -> str:
    """Normalised hash used to guarantee per-project uniqueness."""
    norm = title.strip().lower()
    for step in steps:
        norm += "|" + step["keyword"].lower() + ":" + re.sub(r"\s+", " ", step["text"].strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def build_context(documents: List[Dict[str, Any]]) -> str:
    parts = []
    for doc in documents:
        parts.append(f"## {doc.get('title', 'Document')}\n{doc.get('content', '')}")
    return "\n\n".join(parts)


def generate_test_cases(
    template: Template,
    documents: List[Dict[str, Any]],
    project: Dict[str, Any],
    num_cases: int,
    existing_hashes: Set[str],
    llm: Optional[LLMClient] = None,
    extra_instructions: str = "",
    document_ids: Optional[List[str]] = None,
) -> List[TestCase]:
    """Generate up to ``num_cases`` unique BDD test cases.

    ``existing_hashes`` are content hashes already present for the project; any
    newly produced duplicate (against existing or freshly generated cases) is
    discarded and regeneration is retried.
    """
    field_gen = FieldGenerator(template.fields, llm=llm)
    synth = BddSynthesizer(llm=llm)
    context = build_context(documents)

    seen: Set[str] = set(existing_hashes)
    results: List[TestCase] = []
    max_attempts = max(num_cases * 6, num_cases + 10)
    attempts = 0

    while len(results) < num_cases and attempts < max_attempts:
        attempts += 1
        fields = field_gen.generate_row(context)
        scenario = synth.synthesize(template, fields, context, extra_instructions)
        h = content_hash(scenario["title"], scenario["steps"])
        if h in seen:
            continue  # duplicate — try again for a genuinely unique case
        seen.add(h)
        steps = [BddStep(**s) for s in scenario["steps"]]
        now = datetime.now(timezone.utc).isoformat()
        tc = TestCase(
            id=f"tc_{uuid.uuid4().hex[:12]}",
            project_id=project["id"],
            template_id=template.id,
            document_ids=document_ids or [],
            title=scenario["title"],
            steps=steps,
            gherkin=render_gherkin(scenario["title"], scenario["steps"]),
            fields=fields,
            test_phase=getattr(template.test_phase, "value", str(template.test_phase)),
            test_techniques=template.test_techniques,
            priority=scenario.get("priority", "medium"),
            tags=[],
            market=project.get("market", ""),
            platform=project.get("platform", ""),
            content_hash=h,
            status=TestCaseStatus.GENERATED,
            metadata={"generator": "llm" if (llm and llm.available) else "template"},
            created_at=now,
            updated_at=now,
        )
        results.append(tc)

    return results
