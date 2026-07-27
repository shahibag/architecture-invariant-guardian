"""Test new v0.2 domain models for correctness and validation."""

import pytest
from pydantic import ValidationError

from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    ChangedFile,
    Coverage,
    CoverageGap,
    Invariant,
    InvariantScope,
    JudgeCandidate,
    JudgeDecision,
    JudgeRequest,
    JudgeResult,
    ProviderUsage,
    ReviewRequest,
    SafeWarning,
    Severity,
)


# ---------------------------------------------------------------------------
# ChangedFile
# ---------------------------------------------------------------------------
class TestChangedFile:
    def test_valid_added_file(self) -> None:
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="added",
            patch="@@ -0,0 +1 @@\n+public class Foo {}",
            patch_complete=True,
        )
        assert cf.path == "src/main/java/Foo.java"
        assert cf.status == "added"

    def test_patch_can_be_none(self) -> None:
        cf = ChangedFile(
            path="src/main/java/Foo.java", status="removed", patch=None, patch_complete=True
        )
        assert cf.patch is None

    def test_invalid_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ChangedFile(
                path="src/main/java/Foo.java",
                status="deleted",  # not in the literal
                patch=None,
                patch_complete=True,
            )


# ---------------------------------------------------------------------------
# CoverageGap
# ---------------------------------------------------------------------------
class TestCoverageGap:
    def test_minimal_gap(self) -> None:
        gap = CoverageGap(file="src/main/java/Bar.java", reason="excluded by scope")
        assert gap.file == "src/main/java/Bar.java"
        assert "scope" in gap.reason


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------
class TestCoverage:
    def test_defaults(self) -> None:
        cov = Coverage()
        assert cov.evaluated_files == []
        assert cov.skipped_files == []
        assert cov.context_truncated is False

    def test_with_gaps(self) -> None:
        cov = Coverage(
            evaluated_files=["a.java"],
            skipped_files=[CoverageGap(file="b.java", reason="binary")],
            context_truncated=True,
        )
        assert len(cov.evaluated_files) == 1
        assert len(cov.skipped_files) == 1
        assert cov.context_truncated is True


# ---------------------------------------------------------------------------
# ProviderUsage
# ---------------------------------------------------------------------------
class TestProviderUsage:
    def test_minimal(self) -> None:
        pu = ProviderUsage(model="deepseek-v4-flash", prompt_version="guardian-judge-v2")
        assert pu.model == "deepseek-v4-flash"
        assert pu.input_tokens is None
        assert pu.output_tokens is None


# ---------------------------------------------------------------------------
# InvariantScope — rejects malformed globs at model level
# ---------------------------------------------------------------------------
class TestInvariantScopeValidation:
    """P2.1: InvariantScope must reject unsafe/malformed glob patterns."""

    def test_unbalanced_bracket_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scope|bracket|invalid"):
            InvariantScope(languages=["java"], include_paths=["src/[bad"])

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scope|empty|invalid"):
            InvariantScope(languages=["java"], include_paths=[""])

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scope|absolute|invalid"):
            InvariantScope(languages=["java"], include_paths=["/etc/passwd"])

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scope|null|invalid"):
            InvariantScope(languages=["java"], include_paths=["src/\x00evil"])

    def test_traversal_rejected(self) -> None:
        with pytest.raises(ValidationError, match="scope|traversal|invalid"):
            InvariantScope(languages=["java"], include_paths=["../../etc/passwd"])


# ---------------------------------------------------------------------------
# SafeWarning
# ---------------------------------------------------------------------------
class TestSafeWarning:
    def test_minimal(self) -> None:
        sw = SafeWarning(category="provider_failure", message="AI judgment was unavailable")
        assert sw.category == "provider_failure"

    def test_empty_message_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SafeWarning(category="provider_failure", message="")


# ---------------------------------------------------------------------------
# ReviewRequest
# ---------------------------------------------------------------------------
class TestReviewRequest:
    def test_minimal_request(self) -> None:
        inv = Invariant(
            id="no-domain-leak",
            title="No domain leak",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="Rule",
            rationale="Rationale",
            violating_examples="Bad",
            acceptable_examples="Good",
        )
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch="@@ -1 +1 @@\n-old\n+new",
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc123",
            head_sha="def456",
            invariants=[inv],
            changed_files=[cf],
        )
        assert req.base_sha == "abc123"
        assert len(req.changed_files) == 1


# ---------------------------------------------------------------------------
# Assessment — mandatory coverage
# ---------------------------------------------------------------------------
class TestAssessmentMandatoryCoverage:
    """Assessment.coverage is mandatory per the v0.2 spec."""

    def test_assessment_without_coverage_fails(self) -> None:
        with pytest.raises(ValidationError):
            Assessment(status=AssessmentStatus.INCOMPLETE)

    def test_assessment_with_coverage_succeeds(self) -> None:
        a = Assessment(status=AssessmentStatus.INCOMPLETE, coverage=Coverage())
        assert a.status == AssessmentStatus.INCOMPLETE
        assert isinstance(a.coverage, Coverage)

    def test_warnings_are_safe_warnings(self) -> None:
        a = Assessment(
            status=AssessmentStatus.INCOMPLETE,
            coverage=Coverage(),
            warnings=[SafeWarning(category="provider_failure", message="AI unavailable")],
        )
        assert len(a.warnings) == 1
        assert isinstance(a.warnings[0], SafeWarning)


# ---------------------------------------------------------------------------
# AssessmentStatus — uses assessment_incomplete as the public value
# ---------------------------------------------------------------------------
class TestAssessmentStatus:
    def test_incomplete_value(self) -> None:
        assert AssessmentStatus.INCOMPLETE == "assessment_incomplete"

    def test_enum_members(self) -> None:
        values = {m.value for m in AssessmentStatus}
        assert "assessment_incomplete" in values
        assert "no_confirmed_violations" in values
        assert "confirmed_violations" in values


# ---------------------------------------------------------------------------
# JudgeRequest / JudgeResult — bounded provider contract (Defect 3)
# ---------------------------------------------------------------------------
class TestJudgeContract:
    def test_judge_candidate_construction(self) -> None:
        jc = JudgeCandidate(
            index=0,
            invariant_id="no-domain-leak",
            invariant_text="Do not leak entities.\nRationale: stability.",
            file="src/Foo.java",
            start_line=10,
            end_line=10,
            evidence="public OrderEntity get()",
            context_hunk="@@ -10,3 +10,6 @@\n+    public OrderEntity getOrder() {",
        )
        assert jc.index == 0
        assert jc.invariant_text is not None
        assert len(jc.context_hunk) > 0

    def test_judge_request_no_full_diff(self) -> None:
        req = JudgeRequest(
            candidates=[
                JudgeCandidate(
                    index=0,
                    invariant_id="no-domain-leak",
                    invariant_text="Rule text",
                    file="src/Foo.java",
                    start_line=10,
                    end_line=10,
                    evidence="evidence",
                    context_hunk="hunk",
                )
            ]
        )
        # JudgeRequest must NOT have a "diff" field
        assert not hasattr(req, "diff")

    def test_judge_result_with_usage(self) -> None:
        result = JudgeResult(
            decisions=[
                JudgeDecision(
                    candidate_index=0,
                    decision="confirm",
                    why_it_matters="Entity leaks.",
                    suggested_direction="Use DTO.",
                )
            ],
            provider_usage=ProviderUsage(model="test", prompt_version="v2"),
        )
        assert len(result.decisions) == 1
        assert result.provider_usage is not None
        assert result.truncated is False

    def test_judge_result_truncated(self) -> None:
        result = JudgeResult(decisions=[], truncated=True)
        assert result.truncated is True
