"""Engine-level tests through ReviewEngine.assess using in-memory adapters."""

from pathlib import Path

from invariant_guardian.application import ReviewEngine, assess_diff
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    ChangedFile,
    Coverage,
    CoverageGap,
    Invariant,
    InvariantScope,
    ReviewRequest,
    SafeWarning,
    Severity,
)


FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# ReviewEngine.assess — coverage is mandatory
# ---------------------------------------------------------------------------
class TestReviewEngineAssess:
    def test_assess_returns_assessment_with_mandatory_coverage(self) -> None:
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
            patch="@@ -10,0 +11,3 @@\n+    public OrderResponse getOrder() { return null; }",
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )
        engine = ReviewEngine()
        result = engine.assess(req)
        assert isinstance(result, Assessment)
        assert isinstance(result.coverage, Coverage)
        # No candidates expected for safe DTO, so no violations
        assert result.status in (
            AssessmentStatus.NO_CONFIRMED_VIOLATIONS,
            AssessmentStatus.INCOMPLETE,
        )

    def test_assess_with_no_invariants(self) -> None:
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch="@@ -1 +1 @@\n-old\n+new",
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[],
            changed_files=[cf],
        )
        engine = ReviewEngine()
        result = engine.assess(req)
        # Must have mandatory coverage
        assert isinstance(result.coverage, Coverage)
        # No invariants → no files in scope → coverage gaps → INCOMPLETE
        assert result.status == AssessmentStatus.INCOMPLETE

    def test_assess_incomplete_when_out_of_scope_cannot_be_evaluated(self) -> None:
        """When the only Java file is out of scope, coverage records the skip,
        but the assessment should still produce something safe."""
        inv = Invariant(
            id="no-domain-leak",
            title="No domain leak",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/main/java/**"]),
            rule="Rule",
            rationale="Rationale",
            violating_examples="Bad",
            acceptable_examples="Good",
        )
        cf = ChangedFile(
            path="src/test/java/Foo.java",  # outside include_paths
            status="modified",
            patch="@@ -1 +1 @@\n-old\n+new",
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )
        engine = ReviewEngine()
        result = engine.assess(req)
        assert result.coverage.evaluated_files == []
        assert len(result.coverage.skipped_files) >= 1
        # At least one Java file couldn't be evaluated, so INCOMPLETE
        assert result.status == AssessmentStatus.INCOMPLETE

    def test_assess_truncated_patch_yields_incomplete(self) -> None:
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
            patch_complete=False,  # truncated!
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )
        engine = ReviewEngine()
        result = engine.assess(req)
        # Truncated patches make coverage incomplete
        assert result.status == AssessmentStatus.INCOMPLETE
        assert result.coverage.context_truncated or len(result.coverage.skipped_files) > 0

    def test_assess_non_java_file_not_candidate(self) -> None:
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
            path="README.md",
            status="modified",
            patch="@@ -1 +1 @@\n-old\n+new",
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )
        engine = ReviewEngine()
        result = engine.assess(req)
        assert result.candidates == []
        assert len(result.coverage.skipped_files) >= 1


# ---------------------------------------------------------------------------
# assess_diff — backward compatibility
# ---------------------------------------------------------------------------
class TestAssessDiffBackwardCompat:
    def test_existing_clean_behavior_still_works(self) -> None:
        assessment = assess_diff(
            FIXTURES / "invariants",
            (FIXTURES / "clean.diff").read_text(encoding="utf-8"),
        )
        assert assessment.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS
        # coverage is now mandatory
        assert isinstance(assessment.coverage, Coverage)

    def test_existing_monitoring_candidate_still_detected(self) -> None:
        assessment = assess_diff(
            FIXTURES / "invariants",
            (FIXTURES / "temporary_monitoring.diff").read_text(encoding="utf-8"),
        )
        assert assessment.candidates[0].invariant_id == "no-temporary-monitoring"
        assert isinstance(assessment.coverage, Coverage)

    def test_existing_domain_leak_candidate_still_detected(self) -> None:
        assessment = assess_diff(
            FIXTURES / "invariants",
            (FIXTURES / "domain_leak.diff").read_text(encoding="utf-8"),
        )
        assert assessment.candidates[0].invariant_id == "no-domain-leak"
        assert isinstance(assessment.coverage, Coverage)
