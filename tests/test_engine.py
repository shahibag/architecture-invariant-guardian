"""Engine-level tests through ReviewEngine.assess using in-memory adapters."""

from pathlib import Path

from invariant_guardian.application import ReviewEngine, assess_diff
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    ChangedFile,
    Coverage,
    Invariant,
    InvariantScope,
    ReviewRequest,
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

    def test_assess_out_of_scope_file_not_gap(self) -> None:
        """When the only Java file is out of scope, coverage tracks no gaps
        because out-of-scope files are silently excluded."""
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
        # Out-of-scope — not a coverage gap
        assert len(result.coverage.skipped_files) == 0
        # No gaps → not INCOMPLETE
        assert result.status != AssessmentStatus.INCOMPLETE

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
        # Out-of-scope files are not coverage gaps
        assert result.coverage.skipped_files == []


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


# ---------------------------------------------------------------------------
# In-memory adapters for engine tests
# ---------------------------------------------------------------------------

import json
from types import SimpleNamespace


class FakeJudgeResponses:
    def __init__(self, output: dict) -> None:
        self._output = output
        self.request: dict | None = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self._output))
                )
            ],
            usage=None,
        )


class FakeOpenAI:
    def __init__(self, output: dict) -> None:
        self.chat = SimpleNamespace(completions=FakeJudgeResponses(output))


# ---------------------------------------------------------------------------
# Engine with judge — full evaluate flow
# ---------------------------------------------------------------------------
class TestEngineWithJudge:
    def test_engine_with_judge_confirms_violation(self) -> None:
        from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge

        inv = Invariant(
            id="no-domain-leak",
            title="No domain leak",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="Do not leak entities.",
            rationale="Public contracts should remain stable.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -10,0 +11,3 @@\n"
                "+    public OrderEntity getOrder() { return null; }"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )

        # Create judge that confirms the candidate
        fake_client = FakeOpenAI(
            {
                "decisions": [
                    {
                        "candidate_index": 0,
                        "decision": "confirm",
                        "why_it_matters": "Entity leaks.",
                        "suggested_direction": "Use DTO.",
                    }
                ]
            }
        )
        judge = OpenAICompatibleJudge("unused", client=fake_client)

        engine = ReviewEngine()
        result = engine.assess(req, judge=judge)

        assert result.status == AssessmentStatus.CONFIRMED_VIOLATIONS
        assert len(result.violations) == 1
        assert result.violations[0].invariant_id == "no-domain-leak"
        # Coverage must be preserved
        assert isinstance(result.coverage, Coverage)
        assert result.coverage.evaluated_files == ["src/main/java/Foo.java"]

    def test_engine_with_judge_rejects_candidate(self) -> None:
        """Judge rejects a candidate that was detected by regex — candidate
        preserved but no violation."""
        from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge

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
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -10,0 +11,3 @@\n"
                "+    public OrderEntity getOrder() { return null; }"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )

        # Judge rejects the candidate
        fake_client = FakeOpenAI(
            {
                "decisions": [
                    {
                        "candidate_index": 0,
                        "decision": "reject",
                        "why_it_matters": "Not a real leak.",
                        "suggested_direction": "",
                    }
                ]
            }
        )
        judge = OpenAICompatibleJudge("unused", client=fake_client)
        engine = ReviewEngine()
        result = engine.assess(req, judge=judge)

        assert result.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS
        assert result.violations == []
        # Candidates preserved even though judge rejected
        assert len(result.candidates) == 1
        assert isinstance(result.coverage, Coverage)

    def test_engine_with_judge_incomplete_on_failure(self) -> None:
        from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge

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
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -10,0 +11,3 @@\n"
                "+    public OrderEntity getOrder() { return null; }"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )

        # Malformed provider output
        fake_client = FakeOpenAI({"unexpected": True})
        judge = OpenAICompatibleJudge("unused", client=fake_client)
        engine = ReviewEngine()
        result = engine.assess(req, judge=judge)

        # Should be INCOMPLETE but still preserve coverage and candidates
        assert result.status == AssessmentStatus.INCOMPLETE
        assert isinstance(result.coverage, Coverage)
        assert len(result.candidates) >= 1  # candidates preserved
        assert result.coverage.context_truncated is True

    def test_engine_with_judge_no_full_diff_sent(self) -> None:
        from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge

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
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -10,0 +11,3 @@\n"
                "+    public OrderEntity getOrder() { return null; }"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf],
        )

        fake_client = FakeOpenAI(
            {
                "decisions": [
                    {
                        "candidate_index": 0,
                        "decision": "reject",
                        "why_it_matters": "Fine.",
                        "suggested_direction": "",
                    }
                ]
            }
        )
        judge = OpenAICompatibleJudge("unused", client=fake_client)
        engine = ReviewEngine()
        engine.assess(req, judge=judge)

        # The provider request must NOT contain a "diff" key
        sent = fake_client.chat.completions.request
        assert sent is not None, "Provider was never called"
        user_content = json.loads(sent["messages"][1]["content"])
        assert "diff" not in user_content
        assert "candidates" in user_content
