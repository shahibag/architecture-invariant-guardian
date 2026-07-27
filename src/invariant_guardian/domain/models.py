from __future__ import annotations

import re as _re
from enum import StrEnum
from fnmatch import translate as _fnmatch_translate
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, model_validator


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class AssessmentStatus(StrEnum):
    NO_CONFIRMED_VIOLATIONS = "no_confirmed_violations"
    CONFIRMED_VIOLATIONS = "confirmed_violations"
    CANDIDATES_REQUIRE_JUDGMENT = "candidates_require_judgment"
    INCOMPLETE = "assessment_incomplete"


class InvariantScope(BaseModel):
    languages: list[str] = Field(min_length=1)
    include_paths: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_include_paths(self) -> InvariantScope:
        for p in self.include_paths:
            try:
                _re.compile(_fnmatch_translate(p))
            except _re.error as exc:
                raise ValueError(f"invalid scope include_path {p!r}: {exc}") from exc
        return self


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


class Violation(CandidateFinding):
    why_it_matters: str
    suggested_direction: str


# ---------------------------------------------------------------------------
# v0.2 new models
# ---------------------------------------------------------------------------

class ChangedFile(BaseModel):
    """A single file from a pull-request diff listing."""

    path: str
    status: Literal["added", "modified", "removed", "renamed"]
    patch: str | None = None
    patch_complete: bool = True


class CoverageGap(BaseModel):
    """Why a changed file could not be evaluated."""

    file: str
    reason: str


class Coverage(BaseModel):
    """Which in-scope files were evaluated and which were skipped."""

    evaluated_files: list[str] = Field(default_factory=list)
    skipped_files: list[CoverageGap] = Field(default_factory=list)
    context_truncated: bool = False


class ProviderUsage(BaseModel):
    """Token-usage metadata reported by the model provider."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str
    prompt_version: str


class SafeWarning(BaseModel):
    """A sanitised, user-facing warning — never a raw exception."""

    category: str
    message: str = Field(min_length=1)


class ReviewRequest(BaseModel):
    """The unified input to ReviewEngine.assess."""

    base_sha: str
    head_sha: str
    invariants: list[Invariant] = Field(default_factory=list)
    changed_files: list[ChangedFile] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Warning coercion helper — allows old str warnings alongside new SafeWarning
# ---------------------------------------------------------------------------

def _coerce_warning(v: Any) -> SafeWarning | str:
    """Wrap bare strings so old call sites keep working."""
    if isinstance(v, str):
        return SafeWarning(category="general", message=v)
    return v


# ---------------------------------------------------------------------------
# Updated Assessment — coverage is mandatory
# ---------------------------------------------------------------------------

class Assessment(BaseModel):
    status: AssessmentStatus
    candidates: list[CandidateFinding] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)
    coverage: Coverage
    provider_usage: ProviderUsage | None = None
    warnings: list[Annotated[SafeWarning, BeforeValidator(_coerce_warning)]] = Field(
        default_factory=list
    )
