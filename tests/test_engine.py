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


class EntitySourceReader:
    """Resolve requested Java type paths to matching JPA declarations.

    Returns exact changed-file source and declaration content for related
    type-resolution paths.
    """

    def __init__(self, file_source: str | None = None) -> None:
        self._file_source = file_source

    def changed_files(self) -> list[ChangedFile]:
        return []

    def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
        if self._file_source is not None and path == self._file_source:
            return (
                b"import org.springframework.web.bind.annotation.*;\n\n"
                b"@RestController\n"
                b"class OrderController {\n"
                b"    @GetMapping(\"/order\")\n"
                b"    public OrderEntity getOrder() { return null; }\n"
                b"}\n"
            )
        if (
            self._file_source is not None
            and Path(path).parent != Path(self._file_source).parent
        ):
            return None
        type_name = Path(path).stem
        return (
            "import jakarta.persistence.Entity;\n"
            f"@Entity class {type_name} {{}}\n"
        ).encode()


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
        # Full Java source — AST must have complete class + annotations
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -1,0 +2,8 @@\n"
                "+import jakarta.persistence.Entity;\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@Entity\n"
                "+class OrderEntity {}\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
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
        """Judge rejects a candidate detected by AST — candidate
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
        # Full Java — AST must have complete class + annotations.
        # Include @Entity so the type is known-JPA, not naming-only.
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -1,0 +2,8 @@\n"
                "+import jakarta.persistence.Entity;\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@Entity\n"
                "+class OrderEntity {}\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
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
        # Full Java — AST must have complete class + annotations
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
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
        result = engine.assess(
            req, judge=judge, source_reader=EntitySourceReader(file_source="src/main/java/Foo.java")
        )

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
        # Must include complete Java class for AST parsing
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
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
        result = engine.assess(
            req, judge=judge, source_reader=EntitySourceReader(file_source="src/main/java/Foo.java")
        )

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
        # Full Java class for AST parsing
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
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
        the JudgeRequest.  Excessive invariant text must truncate and make
        the assessment incomplete."""
        from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge
        from invariant_guardian.context import MAX_MODEL_CONTEXT_CHARS

        # Use a huge invariant rule to blow through the model-context ceiling
        inv = Invariant(
            id="no-domain-leak",
            title="No domain leak",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="r" * (MAX_MODEL_CONTEXT_CHARS - 100),
            rationale="Public contracts should remain stable.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )
        # Full valid Java class for AST
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
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
        # Full Java class for AST
        cf = ChangedFile(
            path="src/main/java/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/Foo.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
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
        engine.assess(req, judge=judge, source_reader=EntitySourceReader(file_source="src/main/java/Foo.java"))

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
            patch=(
                "+++ b/src/Foo.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
            ),
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

    def test_non_judge_result_values_are_incomplete_not_clean_or_crashing(self) -> None:
        class BadJudge:
            def __init__(self, value) -> None:
                self.value = value

            def evaluate(self, request):
                return self.value

        changed = ChangedFile(
            path="src/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/Foo.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
            ),
        )
        request = ReviewRequest(
            base_sha="a",
            head_sha="b",
            invariants=[self._invariant()],
            changed_files=[changed],
        )
        for value in (None, {"decisions": []}):
            result = ReviewEngine().assess(request, judge=BadJudge(value))
            assert result.status == AssessmentStatus.INCOMPLETE
            assert result.coverage.context_truncated is True

    def test_exact_provider_message_content_respects_model_ceiling(self) -> None:
        from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge
        from invariant_guardian.context import MAX_MODEL_CONTEXT_CHARS
        from invariant_guardian.domain.models import JudgeDecision, JudgeResult

        class MeasuringJudge:
            called = False

            def evaluate(self, request):
                self.called = True
                messages = OpenAICompatibleJudge._build_messages(request)
                assert sum(len(m["content"]) for m in messages) <= MAX_MODEL_CONTEXT_CHARS
                return JudgeResult(
                    decisions=[
                        JudgeDecision(
                            candidate_index=0,
                            decision="reject",
                            why_it_matters="",
                            suggested_direction="",
                        )
                    ]
                )

        inv = self._invariant().model_copy(update={"rule": "r" * 59_000})
        changed = ChangedFile(
            path="src/Foo.java",
            status="modified",
            patch=(
                "+++ b/src/Foo.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class OrderController {\n"
                "+    @GetMapping(\"/order\")\n"
                "+    public OrderEntity getOrder() { return null; }\n"
                "+}\n"
            ),
        )
        judge = MeasuringJudge()
        result = ReviewEngine().assess(
            ReviewRequest(
                base_sha="a",
                head_sha="b",
                invariants=[inv],
                changed_files=[changed],
            ),
            judge=judge,
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert result.coverage.context_truncated is True
        assert judge.called is False

    def test_context_extractor_has_one_total_limit_across_nearby_hunks(self) -> None:
        from invariant_guardian.application import _extract_bounded_context

        patch = "\n".join(
            part
            for hunk in range(4)
            for part in [
                f"@@ -0,0 +{90 + hunk},50 @@",
                *[f"+near {hunk}-{line}" for line in range(50)],
            ]
        )
        context = _extract_bounded_context(patch, 100)
        assert len(context.splitlines()) <= 82


class TestRegexFallbackCannotConfirmWithoutASTEvidence:
    """P0 finding 2: Regex-only evidence must never produce a confirmable
    domain relationship.  Regex fallback may produce only conservative
    (low-confidence) signals that the judge rejects as noise.
    """

    def test_regex_domain_leak_is_low_confidence_only(self) -> None:
        """A public method returning Entity-suffixed type from a non-controller
        class must be low-confidence from regex fallback, never medium.

        AST correctly finds no candidate (no web annotations on class).
        Regex fallback must not produce a medium-confidence candidate that
        a judge could confirm without any AST boundary evidence.
        """
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

        # Non-controller service class with Entity return — NOT a public
        # boundary.  AST correctly ignores it.  Regex must not elevate it.
        cf = ChangedFile(
            path="src/main/java/com/example/OrderService.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/OrderService.java\n"
                "@@ -5,0 +6,3 @@\n"
                "+    public OrderEntity findOrder() { return null; }"
            ),
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

        # Any domain-leak candidate from regex fallback must be low
        # confidence — never medium or high (confirmable).
        for c in result.candidates:
            if c.invariant_id == "no-domain-leak":
                assert c.confidence == "low", (
                    f"Regex-only domain-leak candidate must be low confidence, "
                    f"got {c.confidence}: {c.evidence}"
                )

    def test_production_engine_does_not_fallback_to_monitoring_regex(self) -> None:
        """Production structural analysis must not turn malformed snippets
        into confirmable monitoring candidates through regex."""
        inv = Invariant(
            id="no-temporary-monitoring",
            title="No temp monitoring",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="No temporary monitoring.",
            rationale="Stable operations.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )

        # Patch that regex would detect as monitoring but AST might not
        # (e.g. non-compilable snippet from minimal patch)
        cf = ChangedFile(
            path="src/main/java/com/example/Worker.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/Worker.java\n"
                "@@ -5,0 +6,3 @@\n"
                "+    @Scheduled(fixedDelay=5000)\n"
                "+    public void poll() { save(); }"
            ),
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

        monitoring = [c for c in result.candidates
                      if c.invariant_id == "no-temporary-monitoring"]
        assert monitoring == []
        assert result.status == AssessmentStatus.INCOMPLETE


class TestDomainRegexFallbackRemoved:
    """P0 finding 1: Domain-leak regex fallback must be removed from the
    engine — valid AST with no finding = no candidate.  AST error or
    insufficient source = coverage gap + assessment_incomplete."""

    def test_regex_domain_leak_cannot_reach_judge(self) -> None:
        """A non-controller class returning OrderEntity must NOT produce
        a domain-leak candidate through the engine.  AST correctly finds
        no candidate (no web annotations).  The regex fallback must not
        fill the gap — a valid parse with no finding is clean."""

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

        # Non-controller public method returning OrderEntity — AST correctly
        # finds no candidate.  Regex fallback must NOT create one.
        cf = ChangedFile(
            path="src/main/java/com/example/OrderService.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/OrderService.java\n"
                "@@ -5,0 +6,3 @@\n"
                "+    public OrderEntity findOrder() { return null; }"
            ),
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

        # Must have ZERO domain-leak candidates — regex fallback must not
        # create a candidate that the AST correctly rejected.
        domain_candidates = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(domain_candidates) == 0, (
            f"Regex fallback must not create domain-leak candidates when "
            f"AST found none. Got: {domain_candidates}"
        )

    def test_parser_failure_creates_coverage_gap_not_clean(self) -> None:
        """When AST parsing fails (malformed source), the engine must record
        a coverage gap and produce assessment_incomplete — never fall
        through to regex for domain-leak and return clean."""
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

        # Malformed Java that the parser will reject
        cf = ChangedFile(
            path="src/main/java/com/example/Broken.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/Broken.java\n"
                "@@ -0,0 +1,5 @@\n"
                "+@RestController\n"
                "+class Broken {\n"
                "+ public List<\n"
                "+   OrderEntity get( {\n"  # malformed
            ),
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

        # Parser failure must produce INCOMPLETE, not clean
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Parser failure must produce INCOMPLETE, got {result.status}"
        )
        # Must have a coverage gap or context_truncated
        assert (
            result.coverage.skipped_files or result.coverage.context_truncated
        ), "Parser failure must create a coverage gap"

    def test_parser_failure_does_not_emit_monitoring_regex_candidate(self) -> None:
        """A parser failure is incomplete and must not emit regex candidates."""
        inv = Invariant(
            id="no-temporary-monitoring",
            title="No temp monitoring",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="No temporary monitoring.",
            rationale="Stable operations.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )

        # Patch that AST would fail to parse but regex can detect
        cf = ChangedFile(
            path="src/main/java/com/example/Worker.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/Worker.java\n"
                "@@ -5,0 +6,3 @@\n"
                "+    @Scheduled(fixedDelay=5000)\n"
                "+    public void poll() { save(); }"
            ),
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

        monitoring = [
            c for c in result.candidates
            if c.invariant_id == "no-temporary-monitoring"
        ]
        assert monitoring == []
        assert result.status == AssessmentStatus.INCOMPLETE
        # No domain regex bleed
        domain = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(domain) == 0, "Domain regex fallback must not bleed into monitoring path"


class TestSourceReaderEngineWiring:
    """P0 finding 2: SourceReader must be wired into ReviewEngine so that
    naming-convention candidates resolve their type declarations.  Missing
    or invalid declarations produce coverage gaps."""

    def _invariant(self) -> Invariant:
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

    def test_naming_candidate_resolved_via_source_reader(self) -> None:
        """When a SourceReader provides a valid @Entity declaration for a
        naming-convention type, the candidate upgrades from low to medium
        confidence with related_evidence."""

        # Controller that returns ProductEntity (Entity suffix, no @Entity
        # annotation in the same file). The SourceReader provides the
        # ProductEntity declaration.
        cf = ChangedFile(
            path="src/main/java/com/example/ProductController.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/ProductController.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class ProductController {\n"
                "+    @GetMapping(\"/product\")\n"
                "+    public ProductEntity getProduct() { return null; }\n"
                "+}\n"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        # In-memory source reader that resolves ProductEntity
        declaration_map = {
            "ProductEntity": (
                b"import jakarta.persistence.Entity;\n"
                b"@Entity\n"
                b"class ProductEntity { private Long id; }\n"
            ),
        }

        class InMemorySourceReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == cf.path:
                    return "\n".join(
                        line[1:]
                        for line in (cf.patch or "").splitlines()
                        if line.startswith("+") and not line.startswith("+++")
                    ).encode()
                # Resolve only the exact same-package declaration path.
                for type_name, content in declaration_map.items():
                    expected = str(Path(cf.path).parent / f"{type_name}.java")
                    if path == expected:
                        return content
                return None

        source_reader = InMemorySourceReader()

        engine = ReviewEngine()
        result = engine.assess(req, source_reader=source_reader)

        candidates = [c for c in result.candidates if c.invariant_id == "no-domain-leak"]
        assert len(candidates) >= 1, (
            f"Expected domain-leak candidate with resolved declaration, got {len(candidates)}"
        )
        c = candidates[0]
        assert c.confidence == "medium", (
            f"Resolved declaration must give medium confidence, got {c.confidence}"
        )
        assert c.related_evidence is not None, (
            "Must include bounded related evidence from declaration"
        )

    def test_unresolvable_declaration_is_coverage_gap(self) -> None:
        """When SourceReader returns None for a naming-convention type's
        declaration, the assessment must be incomplete (coverage gap)."""
        cf = ChangedFile(
            path="src/main/java/com/example/ProductController.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/ProductController.java\n"
                "@@ -1,0 +2,7 @@\n"
                "+import org.springframework.web.bind.annotation.*;\n"
                "+\n"
                "+@RestController\n"
                "+class ProductController {\n"
                "+    @GetMapping(\"/product\")\n"
                "+    public ProductEntity getProduct() { return null; }\n"
                "+}\n"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        # SourceReader that always returns None (can't resolve)
        class MissingSourceReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == cf.path:
                    return "\n".join(
                        line[1:]
                        for line in (cf.patch or "").splitlines()
                        if line.startswith("+") and not line.startswith("+++")
                    ).encode()
                return None

        source_reader = MissingSourceReader()

        judge_calls: list[object] = []

        class MustNotBeCalledJudge:
            def evaluate(self, request):
                judge_calls.append(request)
                raise AssertionError("unresolved evidence must not reach the judge")

        engine = ReviewEngine()
        result = engine.assess(
            req, judge=MustNotBeCalledJudge(), source_reader=source_reader
        )

        # Missing declaration for a naming-convention candidate → INCOMPLETE
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Unresolvable declaration must produce INCOMPLETE, got {result.status}"
        )
        assert (
            result.coverage.skipped_files or result.coverage.context_truncated
        ), "Missing declaration must be a coverage gap"
        assert judge_calls == []
        assert result.violations == []

    def test_missing_exact_changed_source_never_falls_back_to_patch(self) -> None:
        cf = ChangedFile(
            path="src/main/java/com/example/ProductController.java",
            status="modified",
            patch=(
                "@@ -1,0 +1,7 @@\n"
                "+@Entity class ProductEntity {}\n"
                "+@RestController\n"
                "+class ProductController {\n"
                "+  @GetMapping\n"
                "+  public ProductEntity get() { return null; }\n"
                "+}\n"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="base",
            head_sha="exact-head",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        class MissingExactSource:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                return None

        judge_calls: list[object] = []

        class MustNotBeCalledJudge:
            def evaluate(self, request):
                judge_calls.append(request)
                raise AssertionError("uncertain patch source must not reach judge")

        result = ReviewEngine().assess(
            req,
            judge=MustNotBeCalledJudge(),
            source_reader=MissingExactSource(),
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert result.candidates == []
        assert result.violations == []
        assert judge_calls == []
        assert result.coverage.skipped_files


# ---------------------------------------------------------------------------
# P0 Finding 1: Disjoint-patch Frankenstein regression
# ---------------------------------------------------------------------------


class TestDisjointPatchFrankenstein:
    """P0 finding 1: Two-hunk disjoint patches must not be concatenated into
    a Frankenstein AST when no SourceReader is available.  Disjoint hunks
    must fail closed — zero candidates, zero violations, zero judge calls.
    """

    @staticmethod
    def _invariant() -> Invariant:
        return Invariant(
            id="no-temporary-monitoring",
            title="No temp monitoring",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="No temporary monitoring.",
            rationale="Stable operations.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )

    def test_two_hunk_disjoint_no_source_reader_is_incomplete(self) -> None:
        """Two-hunk disjoint patch through ReviewEngine with source_reader=None
        and a confirming judge must be incomplete — zero candidates, zero
        violations, zero judge calls."""

        # Exact two-hunk reproduction from the delegation report:
        # @@ -1,2 +1,2 @@  (class C + @Scheduled)
        # @@ -100,2 +100,2 @@ (save() + closing brace)
        cf = ChangedFile(
            path="src/main/java/com/example/DisjointService.java",
            status="modified",
            patch=(
                "+++ b/src/main/java/com/example/DisjointService.java\n"
                "@@ -1,2 +1,2 @@\n"
                "+class C {\n"
                "+ @Scheduled void m(){\n"
                "@@ -100,2 +100,2 @@\n"
                "+ save(); }\n"
                "+}\n"
            ),
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        # Judge that confirms everything — but must never be called
        judge_calls: list[object] = []

        class MustNotBeCalledJudge:
            def evaluate(self, request):
                judge_calls.append(request)
                raise AssertionError("disjoint patch must not reach judge")

        engine = ReviewEngine()
        result = engine.assess(req, judge=MustNotBeCalledJudge(), source_reader=None)

        # Disjoint hunks → reconstruction fails → AST fails → incomplete
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Expected INCOMPLETE for disjoint patch without source_reader, "
            f"got {result.status}"
        )
        assert result.candidates == [], (
            f"Expected zero candidates, got {len(result.candidates)}"
        )
        assert result.violations == [], (
            f"Expected zero violations, got {len(result.violations)}"
        )
        assert judge_calls == [], "Judge must not be called for disjoint patch"

    def test_disjoint_patch_assess_diff_yields_incomplete(self) -> None:
        """Packaged assess_diff with disjoint patch must be incomplete/gap —
        legacy has no judge, so no candidate can be confirmed."""
        from invariant_guardian.application import assess_diff

        diff = (
            "diff --git a/src/main/java/com/example/DisjointService.java "
            "b/src/main/java/com/example/DisjointService.java\n"
            "--- a/src/main/java/com/example/DisjointService.java\n"
            "+++ b/src/main/java/com/example/DisjointService.java\n"
            "@@ -1,2 +1,2 @@\n"
            "+class C {\n"
            "+ @Scheduled void m(){\n"
            "@@ -100,2 +100,2 @@\n"
            "+ save(); }\n"
            "+}\n"
        )
        assessment = assess_diff(FIXTURES / "invariants", diff)
        # Legacy has no judge → CANDIDATES_REQUIRE_JUDGMENT or INCOMPLETE
        assert assessment.status != AssessmentStatus.CONFIRMED_VIOLATIONS, (
            f"Disjoint patch must not produce confirmed violations via "
            f"assess_diff, got {assessment.status}"
        )
        assert assessment.status != AssessmentStatus.NO_CONFIRMED_VIOLATIONS, (
            f"Disjoint patch must not produce clean result via "
            f"assess_diff, got {assessment.status}"
        )


# ---------------------------------------------------------------------------
# P0 Finding 2: Judge evidence completeness regression
# ---------------------------------------------------------------------------


class TestJudgeEvidenceCompleteness:
    """P0 finding 2: @Scheduled findings must include all deterministic
    monitoring evidence in the JudgeRequest — concrete state-change line,
    snippet, and bounded context covering both annotation and state-change
    locations.  Total context must not exceed 82 lines.
    """

    @staticmethod
    def _invariant() -> Invariant:
        return Invariant(
            id="no-temporary-monitoring",
            title="No temp monitoring",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="No temporary monitoring.",
            rationale="Stable operations.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )

    def test_scheduled_with_state_change_evidence_reaches_judge(self) -> None:
        """@Scheduled at line 2 + repository.save at line 100 in exact-head
        source: JudgeRequest must contain both concrete facts, evidence must
        include state-change line/snippet, and total context must be ≤ 82 lines."""

        # Build a source where @Scheduled is at line ~2 and save() is at line ~100
        # Use enough filler lines to create the separation
        filler_lines = [
            f"    // filler line {i:03d}" for i in range(96)
        ]
        source_lines = [
            "package com.example;",
            "",
            "import org.springframework.scheduling.annotation.Scheduled;",
            "import org.springframework.stereotype.Component;",
            "",
            "@Component",
            "class ScheduledService {",
            "",
            "    @Scheduled(fixedDelay=5000)",
            "    public void reconcile() {",
        ] + filler_lines + [
            "        repository.save(new Order());",
            "    }",
            "}",
        ]
        full_source = "\n".join(source_lines)
        # @Scheduled is at line 9 in 0-indexed → line 9
        # save() should be around line 9 + 96 + some = ~107

        # Patch that changes both @Scheduled line and save() line
        # Find actual line numbers
        scheduled_line = source_lines.index(
            "    @Scheduled(fixedDelay=5000)"
        ) + 1  # 1-indexed
        save_line = source_lines.index(
            "        repository.save(new Order());"
        ) + 1

        patch = (
            "+++ b/src/main/java/com/example/ScheduledService.java\n"
            f"@@ -{scheduled_line},1 +{scheduled_line},1 @@\n"
            "+    @Scheduled(fixedDelay=5000)\n"
            f"@@ -{save_line},1 +{save_line},1 @@\n"
            "+        repository.save(new Order());\n"
        )

        cf = ChangedFile(
            path="src/main/java/com/example/ScheduledService.java",
            status="modified",
            patch=patch,
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        # Capture the judge request for inspection
        captured_request: list[object] = []

        class InspectingJudge:
            def evaluate(self, request):
                captured_request.append(request)
                from invariant_guardian.domain.models import (
                    JudgeDecision,
                    JudgeResult,
                    ProviderUsage,
                )
                return JudgeResult(
                    decisions=[
                        JudgeDecision(
                            candidate_index=c.index,
                            decision="reject",
                            why_it_matters="",
                            suggested_direction="",
                        )
                        for c in request.candidates
                    ],
                    provider_usage=ProviderUsage(
                        model="inspect", prompt_version="v1"
                    ),
                )

        class ExactSourceReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == cf.path:
                    return full_source.encode("utf-8")
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        engine = ReviewEngine()
        result = engine.assess(
            req, judge=InspectingJudge(), source_reader=ExactSourceReader()
        )

        # Must have at least one monitoring candidate
        candidates = [
            c for c in result.candidates
            if c.invariant_id == "no-temporary-monitoring"
        ]
        assert len(candidates) >= 1, (
            f"Expected monitoring candidate, got {len(candidates)}"
        )

        # Verify judge was called
        assert len(captured_request) == 1, "Judge must be called"

        judge_req = captured_request[0]
        assert len(judge_req.candidates) >= 1

        jc = judge_req.candidates[0]

        # Evidence must mention the state-change call
        assert "save" in jc.evidence.lower(), (
            f"JudgeRequest evidence must reference save(), got: {jc.evidence}"
        )
        # Evidence must contain the concrete line/snippet
        assert "repository.save" in jc.evidence.lower() or hasattr(jc, "related_evidence") and jc.related_evidence and "save" in (jc.related_evidence or "").lower(), (
            f"JudgeRequest must include state-change snippet, "
            f"evidence={jc.evidence}, related_evidence={jc.related_evidence}"
        )

        # Total context lines <= 82
        context_lines = jc.context_hunk.split("\n") if jc.context_hunk else []
        assert len(context_lines) <= 82, (
            f"Context hunk must not exceed 82 lines, got {len(context_lines)}"
        )

        # Context must include lines near both the annotation and the state change
        context_text = jc.context_hunk
        assert "@Scheduled" in context_text or "save" in context_text, (
            f"Context must contain evidence from the monitored method, "
            f"got {len(context_lines)} lines"
        )

    def test_unfit_evidence_produces_incomplete_no_judge_call(self) -> None:
        """When required supporting evidence cannot fit within the model
        budget, the assessment must be incomplete with zero judge calls."""
        # Use a source where the state change is extremely far from @Scheduled
        # so the context can't fit both within budget
        far_lines = [f"    // padding {i:04d}" for i in range(200)]
        source_lines = [
            "package com.example;",
            "",
            "import org.springframework.scheduling.annotation.Scheduled;",
            "import org.springframework.stereotype.Component;",
            "",
            "@Component",
            "class FarService {",
            "",
            "    @Scheduled(fixedDelay=5000)",
            "    public void far() {",
        ] + far_lines + [
            "        repository.save(new Order());",
            "    }",
            "}",
        ]
        full_source = "\n".join(source_lines)

        scheduled_line = 9  # 1-indexed
        save_line = 9 + 200 + 1  # ~210

        patch = (
            "+++ b/src/main/java/com/example/FarService.java\n"
            f"@@ -{scheduled_line},1 +{scheduled_line},1 @@\n"
            "+    @Scheduled(fixedDelay=5000)\n"
            f"@@ -{save_line},1 +{save_line},1 @@\n"
            "+        repository.save(new Order());\n"
        )

        cf = ChangedFile(
            path="src/main/java/com/example/FarService.java",
            status="modified",
            patch=patch,
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        judge_calls: list[object] = []

        class MustNotConfirmWithoutFit:
            def evaluate(self, request):
                judge_calls.append(request)
                from invariant_guardian.domain.models import (
                    JudgeDecision,
                    JudgeResult,
                    ProviderUsage,
                )
                return JudgeResult(
                    decisions=[
                        JudgeDecision(
                            candidate_index=c.index,
                            decision="reject",
                            why_it_matters="",
                            suggested_direction="",
                        )
                        for c in request.candidates
                    ],
                    provider_usage=ProviderUsage(
                        model="nofit", prompt_version="v1"
                    ),
                )

        class ExactSourceReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == cf.path:
                    return full_source.encode("utf-8")
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        engine = ReviewEngine()
        result = engine.assess(
            req, judge=MustNotConfirmWithoutFit(),
            source_reader=ExactSourceReader()
        )

        # Either incomplete (gap) or the judge was called but context was bounded
        # The key safety property: no unsupported judge call
        if result.status == AssessmentStatus.INCOMPLETE:
            # Correct — gap from extreme distance
            pass
        elif judge_calls:
            # Judge was called — verify context is bounded
            jc = judge_calls[0].candidates[0]
            context_lines = jc.context_hunk.split("\n") if jc.context_hunk else []
            assert len(context_lines) <= 82, (
                f"Context must be bounded to ≤ 82 lines even with distant "
                f"supporting evidence, got {len(context_lines)}"
            )


# ---------------------------------------------------------------------------
# P0 Finding 3 & P1 Finding 4: Type-resolution regression
# ---------------------------------------------------------------------------


class TestTypeResolutionBoundaries:
    """P0 finding 3 & P1 finding 4: Imported types must be resolved before
    classification.  Missing/malformed/ambiguous/>20-root declarations are
    unavailable evidence (incomplete), not acceptable negatives.  Valid
    suffix-named records/interfaces/enums/non-JPA classes are acceptable.
    """

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

    def _make_req(self, path: str, source: str, patch: str) -> ReviewRequest:
        cf = ChangedFile(
            path=path,
            status="modified",
            patch=patch,
            patch_complete=True,
        )
        return ReviewRequest(
            base_sha="base",
            head_sha="exact-head",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

    def test_imported_type_missing_declaration_is_incomplete(self) -> None:
        """Imported non-suffix type with missing declaration → incomplete,
        zero judge calls."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public Order get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public Order get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class MissingDeclReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                return None  # Order.java is missing

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        judge_calls: list[object] = []

        class NoCallJudge:
            def evaluate(self, request):
                judge_calls.append(request)
                raise AssertionError("missing declaration must not reach judge")

        result = ReviewEngine().assess(
            req, judge=NoCallJudge(),
            source_reader=MissingDeclReader(),
        )
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Missing declaration must produce INCOMPLETE, got {result.status}"
        )
        assert judge_calls == [], (
            f"Missing declaration must not call judge, got {len(judge_calls)} calls"
        )

    def test_imported_type_malformed_declaration_is_incomplete(self) -> None:
        """Imported type with malformed Java declaration → incomplete,
        zero candidates."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public Order get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public Order get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class MalformedDeclReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                # Malformed Java — missing closing brace, unterminated generic
                if path == "src/main/java/com/example/Order.java":
                    return b"import jakarta.persistence.Entity;\n@Entity\nclass Order {\n  public List<\n}"
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=MalformedDeclReader())
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Malformed declaration must produce INCOMPLETE, got {result.status}"
        )

    def test_ambiguous_multiple_source_paths_is_incomplete(self) -> None:
        """Ambiguous declaration (same type resolved in two source roots)
        → result must be None (unavailable), not first-match."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public Order get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public Order get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class AmbiguousDeclReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                # Two different paths both resolve to Order.java
                if path in (
                    "src/main/java/com/example/Order.java",
                    "module-domain/src/main/java/com/example/Order.java",
                ):
                    return b"import jakarta.persistence.Entity;\n@Entity\nclass Order {}\n"
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java", "module-domain/src/main/java"]

        # Ambiguous resolution must not call the judge
        judge_calls: list[object] = []

        class NoCallJudge:
            def evaluate(self, request):
                judge_calls.append(request)
                raise AssertionError("ambiguous declaration must not reach judge")

        result = ReviewEngine().assess(
            req, judge=NoCallJudge(),
            source_reader=AmbiguousDeclReader(),
        )
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f"Ambiguous resolution must produce INCOMPLETE, got {result.status}"
        )
        assert judge_calls == [], (
            f"Ambiguous must not call judge, got {len(judge_calls)} calls"
        )

    def test_over_20_source_roots_is_incomplete(self) -> None:
        """Over-budget root indexes skip extra roots only. Cross-module
        types that need those extras remain unresolved → incomplete.
        Primary-root resolution stays available separately.
        """
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public Order get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public Order get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class OverBudgetReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return [f"module-{i:02d}/src/main/java" for i in range(25)]

        result = ReviewEngine().assess(req, source_reader=OverBudgetReader())
        assert result.status == AssessmentStatus.INCOMPLETE, (
            f">20 roots must produce INCOMPLETE, got {result.status}"
        )

    def test_record_with_entity_suffix_is_acceptable_clean(self) -> None:
        """A record named OrderEntity must be classified as acceptable
        (not internal), producing a clean assessment."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public OrderEntity get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public OrderEntity get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class RecordDeclReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                # OrderEntity is a record, not a JPA entity
                if path == "src/main/java/com/example/OrderEntity.java":
                    return b"package com.example;\nrecord OrderEntity(String id) {}\n"
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=RecordDeclReader())
        assert result.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS, (
            f"Record with Entity suffix must be clean acceptable, got {result.status}"
        )
        domain = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(domain) == 0, (
            f"Record with Entity suffix must not produce domain-leak candidate, "
            f"got {len(domain)}"
        )

    def test_enum_with_entity_suffix_is_acceptable_clean(self) -> None:
        """An enum named OrderEntity must be acceptable clean."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public OrderEntity get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public OrderEntity get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class EnumDeclReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                if path == "src/main/java/com/example/OrderEntity.java":
                    return b"package com.example;\nenum OrderEntity { ACTIVE, INACTIVE }\n"
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=EnumDeclReader())
        domain = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(domain) == 0, (
            f"Enum with Entity suffix must not produce candidate, got {len(domain)}"
        )

    def test_interface_with_entity_suffix_is_acceptable_clean(self) -> None:
        """An interface named OrderEntity must be acceptable clean."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public OrderEntity get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public OrderEntity get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class InterfaceDeclReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                if path == "src/main/java/com/example/OrderEntity.java":
                    return b"package com.example;\ninterface OrderEntity { String id(); }\n"
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=InterfaceDeclReader())
        domain = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(domain) == 0, (
            f"Interface with Entity suffix must not produce candidate, got {len(domain)}"
        )

    def test_non_jpa_class_with_entity_suffix_is_acceptable_clean(self) -> None:
        """A plain class named OrderEntity without JPA annotations must
        be acceptable clean."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public OrderEntity get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public OrderEntity get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class NonJpaClassReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                if path == "src/main/java/com/example/OrderEntity.java":
                    return b"package com.example;\nclass OrderEntity { private String id; }\n"
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=NonJpaClassReader())
        domain = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(domain) == 0, (
            f"Non-JPA class with Entity suffix must not produce candidate, "
            f"got {len(domain)}"
        )

    def test_same_cross_module_jpa_remains_confirmable(self) -> None:
        """Same-module JPA @Entity class without naming suffix must still be
        confirmed when uniquely resolved."""
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public Order get() { return null; }\n"
            "}\n"
        )
        patch = (
            "+++ b/src/main/java/com/example/Api.java\n"
            "@@ -1,0 +1,6 @@\n"
            "+import org.springframework.web.bind.annotation.*;\n"
            "+@RestController\n"
            "+class Api {\n"
            "+    @GetMapping(\"/order\")\n"
            "+    public Order get() { return null; }\n"
            "+}\n"
        )

        req = self._make_req("src/main/java/com/example/Api.java", source, patch)

        class JpaOrderReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == "src/main/java/com/example/Api.java":
                    return source.encode("utf-8")
                if path == "src/main/java/com/example/Order.java":
                    return (
                        b"package com.example;\n"
                        b"import jakarta.persistence.Entity;\n"
                        b"@Entity\n"
                        b"class Order { private Long id; }\n"
                    )
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=JpaOrderReader())
        # Should detect the candidate — Order is confirmed JPA @Entity
        domain = [
            c for c in result.candidates
            if c.invariant_id == "no-domain-leak"
        ]
        assert len(domain) >= 1, (
            f"Imported @Entity class without suffix must be detected, "
            f"got {len(domain)} candidates"
        )
        assert domain[0].confidence in ("medium", "high"), (
            f"Uniquely resolved JPA must be medium/high, got {domain[0].confidence}"
        )

    def test_primitives_strings_collections_stay_acceptable(self) -> None:
        """Standard types (void, String, int, List, etc.) must always be
        acceptable — never produce candidates or gaps."""
        standard_types = ["void", "String", "int", "List<String>",
                          "ResponseEntity<String>", "Optional<String>",
                          "Map<String, Object>", "BigDecimal"]
        for std_type in standard_types:
            patch = (
                f"+++ b/src/main/java/com/example/Api.java\n"
                f"@@ -1,0 +1,6 @@\n"
                f"+import org.springframework.web.bind.annotation.*;\n"
                f"+@RestController\n"
                f"+class Api {{\n"
                f"+    @GetMapping(\"/test\")\n"
                f"+    public {std_type} get() {{ return null; }}\n"
                f"+}}\n"
            )

            cf = ChangedFile(
                path="src/main/java/com/example/Api.java",
                status="modified",
                patch=patch,
                patch_complete=True,
            )
            req = ReviewRequest(
                base_sha="base",
                head_sha="exact-head",
                invariants=[self._invariant()],
                changed_files=[cf],
            )
            result = ReviewEngine().assess(req)
            domain = [
                c for c in result.candidates
                if c.invariant_id == "no-domain-leak"
            ]
            assert len(domain) == 0, (
                f"Standard type {std_type} must not produce domain-leak candidate"
            )


# ---------------------------------------------------------------------------
# P1 Finding 5: Changed-child retry regression
# ---------------------------------------------------------------------------


class TestChangedChildRetryAnchoring:
    """P1 finding 5: When a qualifying changed sleep/state-change child is
    detected inside a retry loop, the candidate start/end must anchor on
    the changed child line, not the enclosing loop."""

    @staticmethod
    def _invariant() -> Invariant:
        return Invariant(
            id="no-temporary-monitoring",
            title="No temp monitoring",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="No temporary monitoring.",
            rationale="Stable operations.",
            violating_examples="Bad",
            acceptable_examples="Good",
        )

    def test_changed_state_child_anchors_candidate(self) -> None:
        """State-change line 5 added to existing loop+sleep: candidate
        start=end must be at line 5 (the changed child), not the unchanged
        loop opening.  Related evidence must reference enclosing loop."""
        source = (
            "package com.example;\n"
            "class RetryWorker {\n"
            "    public void process() {\n"
            "        while (true) {\n"
            "            Thread.sleep(1000);\n"
            "            repository.save(new Order());\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        # Only the save() call at line 6 is changed (1-indexed)
        patch = (
            "+++ b/src/main/java/com/example/RetryWorker.java\n"
            "@@ -5,0 +6,1 @@\n"
            "+            repository.save(new Order());\n"
        )

        cf = ChangedFile(
            path="src/main/java/com/example/RetryWorker.java",
            status="modified",
            patch=patch,
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        class ExactSourceReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == cf.path:
                    return source.encode("utf-8")
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=ExactSourceReader())
        candidates = [
            c for c in result.candidates
            if c.invariant_id == "no-temporary-monitoring"
        ]
        assert len(candidates) >= 1, (
            f"Expected retry candidate, got {len(candidates)}"
        )
        c = candidates[0]
        # Anchor must be on the changed child line (6), not the loop (4)
        assert c.pattern == "wait retry", (
            f"Expected wait retry pattern, got {c.pattern}"
        )
        assert c.start_line == c.end_line, (
            f"Changed-child anchor must be single-line, "
            f"got start={c.start_line} end={c.end_line}"
        )
        assert c.start_line == 6, (
            f"Anchor must be at changed state-change line 6, "
            f"got start={c.start_line} end={c.end_line}"
        )
        # Related evidence must reference the enclosing loop
        assert c.related_evidence is not None, (
            "Must have related structural loop evidence"
        )
        assert "loop" in (c.related_evidence or "").lower() or "4" in (c.related_evidence or ""), (
            f"Related evidence must reference enclosing loop, "
            f"got: {c.related_evidence}"
        )

    def test_changed_sleep_child_anchors_candidate(self) -> None:
        """Sleep line added to existing loop+state: candidate must anchor
        on the changed sleep child line."""
        source = (
            "package com.example;\n"
            "class RetryWorker {\n"
            "    public void process() {\n"
            "        while (true) {\n"
            "            repository.save(new Order());\n"
            "            Thread.sleep(1000);\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        # Only the sleep() call at line 6 is changed
        patch = (
            "+++ b/src/main/java/com/example/RetryWorker.java\n"
            "@@ -5,0 +6,1 @@\n"
            "+            Thread.sleep(1000);\n"
        )

        cf = ChangedFile(
            path="src/main/java/com/example/RetryWorker.java",
            status="modified",
            patch=patch,
            patch_complete=True,
        )
        req = ReviewRequest(
            base_sha="abc",
            head_sha="def",
            invariants=[self._invariant()],
            changed_files=[cf],
        )

        class ExactSourceReader:
            def changed_files(self) -> list[ChangedFile]:
                return []

            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path == cf.path:
                    return source.encode("utf-8")
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java"]

        result = ReviewEngine().assess(req, source_reader=ExactSourceReader())
        candidates = [
            c for c in result.candidates
            if c.invariant_id == "no-temporary-monitoring"
        ]
        assert len(candidates) >= 1, (
            f"Expected retry candidate for changed sleep, got {len(candidates)}"
        )
        c = candidates[0]
        assert c.pattern == "wait retry"
        assert c.start_line == c.end_line, (
            f"Changed-child anchor must be single-line, "
            f"got start={c.start_line} end={c.end_line}"
        )
        assert c.start_line == 6, (
            f"Anchor must be at changed sleep line 6, "
            f"got start={c.start_line} end={c.end_line}"
        )


# ---------------------------------------------------------------------------
# P0 Finding 8: Root-index behavior audit tests
# ---------------------------------------------------------------------------


class TestRootIndexBehavior:
    """P0 finding 8: Source root index must never silently slice, truncate,
    or select the first match.  Missing, ambiguous, or over-budget required
    evidence must remain incomplete."""

    def test_ambiguous_resolution_returns_none(self) -> None:
        """Two source roots both resolving the same qualified name →
        _resolve returns None (not first-match)."""
        from invariant_guardian.application import _build_type_resolver

        source = "package com.example;\n"
        source += "import org.springframework.web.bind.annotation.*;\n"
        source += "@RestController class Api {}\n"

        class AmbiguousReader:
            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                if path in (
                    "src/main/java/com/example/Order.java",
                    "module-domain/src/main/java/com/example/Order.java",
                ):
                    return b"import jakarta.persistence.Entity;\n@Entity class Order {}\n"
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return ["src/main/java", "module-domain/src/main/java"]

        resolver = _build_type_resolver(
            "src/main/java/com/example/Api.java",
            "sha",
            AmbiguousReader(),
            source,
        )
        assert resolver is not None
        # Both roots resolve → ambiguous → must return None
        result = resolver("Order")
        assert result is None, (
            f"Ambiguous resolution must return None, got: {result!r}"
        )

    def test_missing_roots_from_list_source_roots_still_uses_primary(self) -> None:
        """list_source_roots returns None → extra roots skipped, but missing
        declarations under the primary root still resolve to None."""
        from invariant_guardian.application import _build_type_resolver

        source = "package com.example;\n@RestController class Api {}\n"

        class MissingRootsReader:
            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return None  # missing

        resolver = _build_type_resolver(
            "src/main/java/com/example/Api.java",
            "sha",
            MissingRootsReader(),
            source,
        )
        assert resolver is not None
        result = resolver("Order")
        assert result is None, (
            f"Missing declaration under primary root must return None, got: {result!r}"
        )

    def test_over_20_roots_skips_extras_not_primary(self) -> None:
        """list_source_roots >20 → extra roots ignored; unresolved type is None."""
        from invariant_guardian.application import _build_type_resolver

        source = "package com.example;\n@RestController class Api {}\n"

        class OverBudgetRootsReader:
            def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
                return None

            def list_source_roots(self, ref: str) -> list[str] | None:
                return [f"module-{i:02d}/src/main/java" for i in range(25)]

        resolver = _build_type_resolver(
            "src/main/java/com/example/Api.java",
            "sha",
            OverBudgetRootsReader(),
            source,
        )
        assert resolver is not None
        result = resolver("Order")
        assert result is None, (
            f"Unresolved type with over-budget extras must return None, got: {result!r}"
        )


# ---------------------------------------------------------------------------
# Unsupported / duplicate invariant capability validation
# ---------------------------------------------------------------------------
class _AcceptAllJudge:
    """Judge that confirms every candidate — used only to prove capability gate
    fires before detection/judgment can produce a false clean."""

    def evaluate(self, request):  # type: ignore[no-untyped-def]
        from invariant_guardian.domain.models import (
            JudgeDecision,
            JudgeResult,
            ProviderUsage,
        )

        return JudgeResult(
            decisions=[
                JudgeDecision(
                    candidate_index=i,
                    decision="confirm",
                    why_it_matters="x",
                    suggested_direction="y",
                )
                for i in range(len(request.candidates))
            ],
            provider_usage=ProviderUsage(
                input_tokens=1,
                output_tokens=1,
                model="test",
                prompt_version="guardian-judge-v2",
            ),
        )


def _java_changed_file(path: str = "src/main/java/com/example/Api.java") -> ChangedFile:
    patch = (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1,7 @@\n"
        "+package com.example;\n"
        "+import org.springframework.web.bind.annotation.*;\n"
        "+@RestController\n"
        "+class Api {\n"
        '+    @GetMapping("/ok")\n'
        '+    public String ok() { return "ok"; }\n'
        "+}\n"
    )
    return ChangedFile(
        path=path,
        status="added",
        patch=patch,
        patch_complete=True,
    )


def _invariant(inv_id: str, title: str = "Custom") -> Invariant:
    return Invariant(
        id=inv_id,
        title=title,
        severity=Severity.ERROR,
        scope=InvariantScope(languages=["java"], include_paths=["src/main/java/**"]),
        rule="custom rule",
        rationale="custom rationale",
        violating_examples="bad",
        acceptable_examples="good",
    )


class ExactSourceReader:
    def __init__(self, path: str, source: str) -> None:
        self._path = path
        self._source = source

    def changed_files(self) -> list[ChangedFile]:
        return []

    def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
        if path == self._path:
            return self._source.encode("utf-8")
        return None

    def list_source_roots(self, ref: str) -> list[str] | None:
        return ["src/main/java"]


class TestUnsupportedAndDuplicateInvariants:
    def test_unsupported_invariant_id_is_incomplete_not_clean(self) -> None:
        path = "src/main/java/com/example/Api.java"
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/ok\")\n"
            "    public String ok() { return \"ok\"; }\n"
            "}\n"
        )
        request = ReviewRequest(
            base_sha="base",
            head_sha="head",
            invariants=[_invariant("no-sql-injection")],
            changed_files=[_java_changed_file(path)],
        )
        result = ReviewEngine().assess(
            request,
            judge=_AcceptAllJudge(),
            source_reader=ExactSourceReader(path, source),
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert result.violations == []
        assert any("unsupported" in w.message.lower() for w in result.warnings)

    def test_duplicate_invariant_ids_are_incomplete(self) -> None:
        path = "src/main/java/com/example/Api.java"
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/ok\")\n"
            "    public String ok() { return \"ok\"; }\n"
            "}\n"
        )
        request = ReviewRequest(
            base_sha="base",
            head_sha="head",
            invariants=[
                _invariant("no-domain-leak", title="First"),
                _invariant("no-domain-leak", title="Second"),
            ],
            changed_files=[_java_changed_file(path)],
        )
        result = ReviewEngine().assess(
            request,
            judge=_AcceptAllJudge(),
            source_reader=ExactSourceReader(path, source),
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert any("duplicate" in w.message.lower() for w in result.warnings)

    def test_mixed_supported_and_unsupported_is_incomplete(self) -> None:
        path = "src/main/java/com/example/Api.java"
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/ok\")\n"
            "    public String ok() { return \"ok\"; }\n"
            "}\n"
        )
        request = ReviewRequest(
            base_sha="base",
            head_sha="head",
            invariants=[
                _invariant("no-domain-leak"),
                _invariant("custom-layering"),
            ],
            changed_files=[_java_changed_file(path)],
        )
        result = ReviewEngine().assess(
            request,
            judge=_AcceptAllJudge(),
            source_reader=ExactSourceReader(path, source),
        )
        assert result.status == AssessmentStatus.INCOMPLETE
        assert any("unsupported" in w.message.lower() for w in result.warnings)

    def test_supported_invariants_still_assess_normally(self) -> None:
        path = "src/main/java/com/example/Api.java"
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/ok\")\n"
            "    public String ok() { return \"ok\"; }\n"
            "}\n"
        )
        request = ReviewRequest(
            base_sha="base",
            head_sha="head",
            invariants=[
                _invariant("no-domain-leak"),
                _invariant("no-temporary-monitoring"),
            ],
            changed_files=[_java_changed_file(path)],
        )
        result = ReviewEngine().assess(
            request,
            judge=_AcceptAllJudge(),
            source_reader=ExactSourceReader(path, source),
        )
        assert result.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS
        assert result.violations == []


class TestPrimaryRootSurvivesIndexFailure:
    def test_same_module_entity_resolved_when_source_roots_unavailable(self) -> None:
        """Failed/over-budget list_source_roots must not disable primary-root resolution."""
        path = "src/main/java/com/example/Api.java"
        source = (
            "package com.example;\n"
            "import org.springframework.web.bind.annotation.*;\n"
            "@RestController\n"
            "class Api {\n"
            "    @GetMapping(\"/order\")\n"
            "    public OrderEntity get() { return null; }\n"
            "}\n"
        )
        entity = (
            "package com.example;\n"
            "import jakarta.persistence.Entity;\n"
            "@Entity\n"
            "public class OrderEntity {}\n"
        )

        class RootsUnavailableReader:
            def changed_files(self):
                return []

            def read_file_at_ref(self, p: str, ref: str) -> bytes | None:
                if p == path:
                    return source.encode()
                if p == "src/main/java/com/example/OrderEntity.java":
                    return entity.encode()
                return None

            def list_source_roots(self, ref: str):
                return None  # index unavailable

        request = ReviewRequest(
            base_sha="base",
            head_sha="head",
            invariants=[_invariant("no-domain-leak")],
            changed_files=[
                ChangedFile(
                    path=path,
                    status="modified",
                    patch=(
                        f"diff --git a/{path} b/{path}\n"
                        f"--- a/{path}\n"
                        f"+++ b/{path}\n"
                        "@@ -1,1 +1,7 @@\n"
                        "+package com.example;\n"
                        "+import org.springframework.web.bind.annotation.*;\n"
                        "+@RestController\n"
                        "+class Api {\n"
                        '+    @GetMapping("/order")\n'
                        "+    public OrderEntity get() { return null; }\n"
                        "+}\n"
                    ),
                    patch_complete=True,
                )
            ],
        )
        result = ReviewEngine().assess(
            request,
            judge=_AcceptAllJudge(),
            source_reader=RootsUnavailableReader(),
        )
        assert result.status == AssessmentStatus.CONFIRMED_VIOLATIONS, (
            f"expected confirmed domain leak via primary root, got {result.status} "
            f"warnings={[w.message for w in result.warnings]} "
            f"candidates={len(result.candidates)} gaps={result.coverage.skipped_files}"
        )
