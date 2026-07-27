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

    def test_assess_missing_patch_on_in_scope_non_removed_is_incomplete(self) -> None:
        """An in-scope modified Java file with patch=None must produce
        assessment_incomplete — never a clean result."""
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
        # patch=None but patch_complete=True (current GitHub adapter behavior)
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=None,
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
        # Missing patch on non-removed in-scope file → incomplete
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Expected INCOMPLETE, got {result.status} "
            f"(missing patch on in-scope file must never be clean)"
        )
        # Must be tracked as a coverage gap
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

    def test_aggregate_patch_bytes_enforced_not_per_file(self) -> None:
        """MAX_PATCH_BYTES (200,000) must be enforced across ALL in-scope
        patches, not per-file.  Two 120 KB patches (240 KB total) exceed
        the ceiling and must produce an incomplete assessment even when
        a judge is available."""
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
        # Each patch is 120 KB — together they exceed 200 KB
        filler = "// " + "x" * 120_000
        patch_a = "@@ -10,0 +11,3 @@\n+    public OrderEntity getOrder() {}\n" + filler
        patch_b = "@@ -10,0 +11,3 @@\n+    public OrderEntity getOrder() {}\n" + filler
        cf_a = ChangedFile(
            path="src/main/java/A.java",
            status="modified",
            patch=patch_a,
            patch_complete=True,
        )
        cf_b = ChangedFile(
            path="src/main/java/B.java",
            status="modified",
            patch=patch_b,
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv],
            changed_files=[cf_a, cf_b],
        )

        # Even with a judge, aggregate enforcement must trigger incomplete
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
        # Aggregate bytes > MAX_PATCH_BYTES → incomplete
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Expected INCOMPLETE when aggregate patch bytes exceed ceiling, "
            f"got {result.status}"
        )
        assert result.coverage.context_truncated or result.coverage.skipped_files

    def test_extract_bounded_context_excludes_unrelated_hunk_headers(self) -> None:
        """_extract_bounded_context must only include hunk headers that are
        near the target line — unrelated hunk headers inflate context and
        can breach the model-context budget."""
        from invariant_guardian.application import _extract_bounded_context

        # Patch with two hunks: one near line 11, one far away at line 500
        patch = (
            "@@ -10,0 +11,3 @@\n"
            "+    public OrderEntity getOrder() { return null; }\n"
            "@@ -499,0 +500,3 @@\n"
            "+    public void unrelatedHunk() {}\n"
        )
        bounded = _extract_bounded_context(patch, 11)
        # Should include the line near line 11
        assert "getOrder" in bounded
        # Must NOT include the unrelated hunk at line 500 (40 lines away is max)
        assert "unrelatedHunk" not in bounded, (
            f"Unrelated hunk header at line 500 leaked into bounded context:\n{bounded}"
        )
        # Must NOT include the @@ header for the unrelated hunk
        assert "@@ -499" not in bounded, (
            f"Unrelated hunk header leaked into bounded context:\n{bounded}"
        )

    def test_github_shaped_patch_detects_candidates(self) -> None:
        """GitHub per-file patches lack +++ b/<path> headers — the engine
        must normalise them so that candidate detection still works."""
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
        # GitHub-shaped patch: NO +++ b/ header, just hunk + lines
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
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

        # Must detect the domain-leak candidate even without +++ b/ header
        assert len(result.candidates) >= 1, (
            f"Expected ≥1 candidate from GitHub-shaped patch, "
            f"got {len(result.candidates)}; patch was: {cf.patch!r}"
        )
        assert result.candidates[0].invariant_id == "no-domain-leak"
        assert result.candidates[0].file == "src/main/java/Foo.java"

    def test_invariant_scope_isolation(self) -> None:
        """A file in scope for invariant A must NOT enable detectors for
        invariant B.  Each invariant's scope is enforced independently."""
        inv_monitoring = Invariant(
            id="no-temporary-monitoring",
            title="No temp monitoring",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/monitoring/**"]),
            rule="Rule",
            rationale="Rationale",
            violating_examples="Bad",
            acceptable_examples="Good",
        )
        inv_leak = Invariant(
            id="no-domain-leak",
            title="No domain leak",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/api/**"]),
            rule="Rule",
            rationale="Rationale",
            violating_examples="Bad",
            acceptable_examples="Good",
        )
        # This file is ONLY in scope for monitoring, NOT for domain-leak
        cf = ChangedFile(
            path="src/monitoring/java/HealthCheck.java",
            status="modified",
            patch=(
                "@@ -10,0 +11,3 @@\n"
                "+    public OrderEntity getOrder() { return null; }"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[inv_monitoring, inv_leak],
            changed_files=[cf],
        )
        engine = ReviewEngine()
        result = engine.assess(req)

        # Should NOT have any no-domain-leak candidates because the file
        # is not in the domain-leak invariant's scope
        leak_candidates = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(leak_candidates) == 0, (
            f"Scope bleed: got {len(leak_candidates)} no-domain-leak "
            f"candidates from a file outside that invariant's scope. "
            f"Candidates: {result.candidates}"
        )

    def test_load_warnings_make_assessment_incomplete(self, tmp_path: Path) -> None:
        """assess_diff must surface invariant-load warnings and produce
        INCOMPLETE when invariant loading produces warnings (even if
        some invariants loaded successfully)."""
        from invariant_guardian.application import assess_diff

        # Create one valid invariant
        valid_md = tmp_path / "valid.md"
        valid_md.write_text(
            "---\n"
            "id: no-domain-leak\n"
            "title: No domain leak\n"
            "severity: error\n"
            "scope:\n"
            "  languages: [java]\n"
            "  include_paths: [src/**]\n"
            "---\n"
            "## Rule\nDo not leak.\n"
            "## Rationale\nStability.\n"
            "## Violating examples\nBad.\n"
            "## Acceptable examples\nGood.\n",
            encoding="utf-8",
        )
        # Create one invalid invariant (missing required section)
        invalid_md = tmp_path / "invalid.md"
        invalid_md.write_text(
            "---\n"
            "id: broken\n"
            "title: Broken\n"
            "severity: error\n"
            "scope:\n"
            "  languages: [java]\n"
            "  include_paths: [src/**]\n"
            "---\n"
            "## Rule\nRule text.\n",
            encoding="utf-8",
        )
        assessment = assess_diff(
            tmp_path,
            (FIXTURES / "clean.diff").read_text(encoding="utf-8"),
        )
        # Load warnings must surface
        assert any(
            "invalid" in w.message.lower() for w in assessment.warnings
        ), f"No load warning found in {assessment.warnings}"
        # Load warnings must force INCOMPLETE
        assert assessment.status == AssessmentStatus.INCOMPLETE, (
            f"Expected INCOMPLETE when invariant loading produced warnings, "
            f"got {assessment.status}"
        )

    def test_engine_validates_judge_result_decision_count(self) -> None:
        """A judge returning empty decisions with candidates present must
        be rejected as incomplete — never fall through to clean."""
        from invariant_guardian.domain.models import (
            JudgeRequest,
            JudgeResult,
            ProviderUsage,
        )

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

        # A non-OpenAI judge that returns empty decisions
        class RogueJudge:
            def evaluate(self, _request: JudgeRequest) -> JudgeResult:
                return JudgeResult(
                    decisions=[],
                    provider_usage=ProviderUsage(
                        model="rogue", prompt_version="v1"
                    ),
                )

        engine = ReviewEngine()
        result = engine.assess(req, judge=RogueJudge())

        # Must be INCOMPLETE — empty decisions with candidates is invalid
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Expected INCOMPLETE from empty decisions, got {result.status}"
        )

    def test_model_context_chars_enforced(self) -> None:
        """MAX_MODEL_CONTEXT_CHARS (60,000) must be enforced when building
        the JudgeRequest.  Excessive context must truncate and make the
        assessment incomplete."""
        from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge
        from invariant_guardian.context import MAX_MODEL_CONTEXT_CHARS

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
        # Create a patch large enough to blow through the model-context
        # ceiling when used as evidence.
        huge_body = "// " + "z" * (MAX_MODEL_CONTEXT_CHARS + 1000)
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "@@ -10,0 +11,3 @@\n"
                "+    public OrderEntity getOrder() {}\n"
                + huge_body
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

        # Model context must be bounded — incomplete when ceiling hit
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Expected INCOMPLETE when model context exceeds "
            f"{MAX_MODEL_CONTEXT_CHARS}, got {result.status}"
        )
        assert result.coverage.context_truncated

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


class TestRecoveryBudgetEnforcement:
    @staticmethod
    def _invariant() -> Invariant:
        return Invariant(
            id="no-domain-leak",
            title="No domain leak",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="Do not leak entities.",
            rationale="Public contracts should remain stable.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )

    def test_files_outside_aggregate_patch_budget_are_not_analyzed(self) -> None:
        from invariant_guardian.context import MAX_PATCH_BYTES

        first = ChangedFile(
            path="src/First.java",
            status="modified",
            patch="@@ -1 +1 @@\n+// " + "x" * (MAX_PATCH_BYTES - 40),
        )
        over_budget = ChangedFile(
            path="src/Second.java",
            status="modified",
            patch="@@ -1 +1 @@\n+public OrderEntity leaked() {}",
        )
        result = ReviewEngine().assess(
            ReviewRequest(
                base_sha="a",
                head_sha="b",
                invariants=[self._invariant()],
                changed_files=[first, over_budget],
            )
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert result.candidates == []

    def test_files_after_changed_file_ceiling_are_not_analyzed(self) -> None:
        clean = [
            ChangedFile(
                path=f"src/Clean{i}.java",
                status="modified",
                patch="@@ -1 +1 @@\n+class Clean {}",
            )
            for i in range(200)
        ]
        hidden = ChangedFile(
            path="src/Hidden.java",
            status="modified",
            patch="@@ -1 +1 @@\n+public OrderEntity leaked() {}",
        )
        result = ReviewEngine().assess(
            ReviewRequest(
                base_sha="a",
                head_sha="b",
                invariants=[self._invariant()],
                changed_files=[*clean, hidden],
            )
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert result.candidates == []

    def test_context_extractor_limits_lines_and_excludes_unrelated_hunks(self) -> None:
        from invariant_guardian.application import _extract_bounded_context

        near = [f"+line {i}" for i in range(1, 201)]
        patch = "\n".join(
            [
                "+++ b/src/Foo.java",
                "@@ -0,0 +1,200 @@",
                *near,
                "@@ -0,0 +1000,1 @@",
                "+UNRELATED_HUNK",
            ]
        )
        context = _extract_bounded_context(patch, 100)
        assert len(context.splitlines()) <= 82
        assert "UNRELATED_HUNK" not in context

    def test_rogue_judge_exception_becomes_incomplete(self) -> None:
        class ExplodingJudge:
            def evaluate(self, request):
                raise RuntimeError("secret provider detail")

        changed = ChangedFile(
            path="src/Foo.java",
            status="modified",
            patch="@@ -1 +1 @@\n+public OrderEntity leaked() {}",
        )
        result = ReviewEngine().assess(
            ReviewRequest(
                base_sha="a",
                head_sha="b",
                invariants=[self._invariant()],
                changed_files=[changed],
            ),
            judge=ExplodingJudge(),
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert "secret provider detail" not in str(result.warnings)
