"""Pydantic models describing the TestGen domain.

The domain is organised around an Enterprise QA workflow:

    Project ──< ContextDocument (versioned, approvable requirements)
            ──< Template        (field variables + BDD/prompt templates)
            ──< TestCase        (generated BDD scenarios, annotated & approved)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #
class ProjectBase(BaseModel):
    name: str
    description: str = ""
    market: str = ""          # e.g. "UK", "Ireland" (HLR6/HLR8 market filters)
    platform: str = ""        # e.g. "Web", "iOS", "Android" (HLR8 platform dropdowns)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectCreate(ProjectBase):
    pass


class Project(ProjectBase):
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# --------------------------------------------------------------------------- #
# Context / requirements documents (HLR1, HLR2)
# --------------------------------------------------------------------------- #
class DocumentStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ARCHIVED = "archived"


class DocumentCreate(BaseModel):
    project_id: str
    title: str
    content: str
    doc_type: str = "requirements"   # requirements | user_story | acceptance_criteria | context
    market: str = ""
    platform: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    id: str
    project_id: str
    title: str
    content: str
    doc_type: str = "requirements"
    market: str = ""
    platform: str = ""
    version: int = 1
    # All versions of a logical document share the same ``family_id`` so we can
    # collate/version/retrieve them together (HLR2).
    family_id: str
    status: DocumentStatus = DocumentStatus.DRAFT
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# --------------------------------------------------------------------------- #
# Templates & field variables (Gym-inspired) (HLR1, HLR3, HLR7)
# --------------------------------------------------------------------------- #
class FieldType(str, Enum):
    """Independently generated variable types (inspired by the qstudio Gym)."""

    ENUM = "enum"                 # pick from a fixed list of allowed values
    SAMPLING = "sampling"         # sample (optionally weighted) from a list
    LLM_GENERATED = "llm_generated"
    EXPRESSION = "expression"     # computed from other fields
    DATE = "date"
    NUMBER = "number"             # int or float within a range
    BOOLEAN = "boolean"
    STRING = "string"             # free static / faker-style string


class FieldDefinition(BaseModel):
    name: str
    field_type: FieldType
    description: str = ""
    # enum / sampling
    sample_values: Optional[List[str]] = None
    weights: Optional[List[float]] = None
    # llm
    llm_prompt: Optional[str] = None
    # expression (python expression over previously generated field names)
    expression: Optional[str] = None
    # date
    date_min: Optional[str] = None
    date_max: Optional[str] = None
    date_format: Optional[str] = None
    # number
    number_min: Optional[float] = None
    number_max: Optional[float] = None
    number_type: str = "float"    # "int" | "float"
    # string
    default: Optional[str] = None
    # constraints / relationships
    required: bool = True
    unique: bool = False
    depends_on: Optional[List[str]] = None


class TestPhase(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    SYSTEM = "system"
    SMOKE = "smoke"
    REGRESSION = "regression"
    UAT = "uat"
    E2E = "e2e"


class OutputDetail(str, Enum):
    HIGH_LEVEL = "high_level"     # title + one-line scenario
    STANDARD = "standard"         # full Given/When/Then
    DETAILED = "detailed"         # GWT + And/But steps, examples, test data


class TemplateCreate(BaseModel):
    project_id: Optional[str] = None   # None => reusable across projects
    name: str
    description: str = ""
    # The Gherkin skeleton. Placeholders ``{field_name}`` are substituted with
    # generated field values. ``{scenario_title}`` / ``{given}`` / ``{when}`` /
    # ``{then}`` are filled by the generator/LLM.
    gherkin_template: str = (
        "Scenario: {scenario_title}\n"
        "  Given {given}\n"
        "  When {when}\n"
        "  Then {then}"
    )
    # The instruction given to the LLM to turn requirements + field values into a
    # BDD scenario. Versioned per platform (HLR7).
    prompt_template: str = ""
    fields: List[FieldDefinition] = Field(default_factory=list)
    test_phase: TestPhase = TestPhase.SYSTEM
    test_techniques: List[str] = Field(default_factory=list)  # e.g. boundary, negative
    output_detail: OutputDetail = OutputDetail.STANDARD
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Template(TemplateCreate):
    id: str
    version: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# --------------------------------------------------------------------------- #
# Test cases, annotations, approval (HLR3, HLR9, HLR10, HLR11)
# --------------------------------------------------------------------------- #
class TestCaseStatus(str, Enum):
    GENERATED = "generated"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"


class AnnotationVerdict(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    NEEDS_CHANGES = "needs_changes"


class Annotation(BaseModel):
    id: str
    author: str = "qa"
    verdict: AnnotationVerdict
    comment: str = ""
    rating: Optional[int] = None      # 1-5 quality rating, feeds HLR5/HLR11
    created_at: Optional[str] = None


class BddStep(BaseModel):
    keyword: str   # Given | When | Then | And | But
    text: str


class TestCase(BaseModel):
    id: str
    project_id: str
    template_id: Optional[str] = None
    document_ids: List[str] = Field(default_factory=list)
    title: str
    steps: List[BddStep] = Field(default_factory=list)
    gherkin: str = ""                 # rendered .feature scenario text
    fields: Dict[str, Any] = Field(default_factory=dict)
    test_phase: str = "system"
    test_techniques: List[str] = Field(default_factory=list)
    priority: str = "medium"
    tags: List[str] = Field(default_factory=list)
    market: str = ""
    platform: str = ""
    # Normalised hash guaranteeing uniqueness within a project (dedup).
    content_hash: str = ""
    status: TestCaseStatus = TestCaseStatus.GENERATED
    annotations: List[Annotation] = Field(default_factory=list)
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    # Multi-round regeneration history (HLR9).
    regeneration_history: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# --------------------------------------------------------------------------- #
# Generation / annotation request payloads
# --------------------------------------------------------------------------- #
class GenerateRequest(BaseModel):
    project_id: str
    template_id: str
    document_ids: List[str] = Field(default_factory=list)
    num_cases: int = 5
    # If true, only approved documents may be used as source context (HLR10).
    require_approved_documents: bool = False
    llm_model: Optional[str] = None
    extra_instructions: str = ""


class AnnotationCreate(BaseModel):
    author: str = "qa"
    verdict: AnnotationVerdict
    comment: str = ""
    rating: Optional[int] = None


class ApprovalRequest(BaseModel):
    approved_by: str = "qa-lead"
    approve: bool = True
    comment: str = ""


class RegenerateRequest(BaseModel):
    feedback: str
    author: str = "qa"
    llm_model: Optional[str] = None
