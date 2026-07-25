from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class AssessmentStatus(StrEnum):
    NO_CONFIRMED_VIOLATIONS = "no_confirmed_violations"
    CANDIDATES_REQUIRE_JUDGMENT = "candidates_require_judgment"
    INCOMPLETE = "assessment_incomplete"


class InvariantScope(BaseModel):
    languages: list[str] = Field(min_length=1)
    include_paths: list[str] = Field(min_length=1)


class Invariant(BaseModel):
    id: str
    title: str
    severity: Severity
    scope: InvariantScope
    rule: str
    rationale: str
    violating_examples: str
    acceptable_examples: str


class CandidateFinding(BaseModel):
    invariant_id: str
    file: str
    start_line: int
    end_line: int
    pattern: str
    evidence: str
    confidence: str


class Assessment(BaseModel):
    status: AssessmentStatus
    candidates: list[CandidateFinding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

