"""Tests for the deterministic (offline) generation engine and uniqueness."""

import os
import tempfile

# Use an isolated temp DB so tests never touch real data.
os.environ.setdefault("TESTGEN_DB_DIR", tempfile.mkdtemp(prefix="testgen-test-"))
os.environ.setdefault("TESTGEN_LLM_PROVIDER", "none")

from app.generation import FieldGenerator, content_hash, generate_test_cases  # noqa: E402
from app.models import FieldDefinition, FieldType, Template  # noqa: E402


def _login_template() -> Template:
    return Template(
        id="tpl_test",
        name="login",
        fields=[
            FieldDefinition(
                name="credential_type",
                field_type=FieldType.ENUM,
                sample_values=["valid", "invalid", "expired", "locked-out"],
            ),
            FieldDefinition(
                name="expected_outcome",
                field_type=FieldType.EXPRESSION,
                expression=(
                    "'be redirected to the dashboard' if credential_type == 'valid' "
                    "else 'see an authentication error'"
                ),
                depends_on=["credential_type"],
            ),
        ],
    )


def test_expression_field_respects_dependencies():
    gen = FieldGenerator(_login_template().fields)
    for _ in range(20):
        row = gen.generate_row()
        if row["credential_type"] == "valid":
            assert "dashboard" in row["expected_outcome"]
        else:
            assert "error" in row["expected_outcome"]


def test_generated_cases_are_unique():
    template = _login_template()
    project = {"id": "prj_test", "name": "Demo", "market": "UK", "platform": "Web"}
    cases = generate_test_cases(
        template=template,
        documents=[{"title": "Login", "content": "User can log in."}],
        project=project,
        num_cases=4,
        existing_hashes=set(),
    )
    hashes = [c.content_hash for c in cases]
    assert len(hashes) == len(set(hashes)), "duplicate test cases were produced"
    # Every case must render a Gherkin scenario with Given/When/Then.
    for c in cases:
        assert c.gherkin.startswith("Scenario:")
        keywords = {s.keyword for s in c.steps}
        assert {"Given", "When", "Then"}.issubset(keywords)


def test_dedup_against_existing_hashes():
    template = _login_template()
    project = {"id": "prj_test2", "name": "Demo2"}
    first = generate_test_cases(template, [], project, num_cases=3, existing_hashes=set())
    existing = {c.content_hash for c in first}
    second = generate_test_cases(template, [], project, num_cases=3, existing_hashes=existing)
    # No case in the second batch may collide with the first.
    assert existing.isdisjoint({c.content_hash for c in second})


def test_content_hash_is_normalised():
    a = content_hash("Title", [{"keyword": "Given", "text": "a  b"}])
    b = content_hash("title", [{"keyword": "given", "text": "a b"}])
    assert a == b
