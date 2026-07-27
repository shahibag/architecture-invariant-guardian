from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    CandidateFinding,
    Coverage,
    CoverageGap,
    Invariant,
    InvariantScope,
    SafeWarning,
    Severity,
    Violation,
)
from invariant_guardian.rendering.comment import (
    MARKER_PREFIX,
    fingerprint,
    render_comment,
)

INVARIANT = Invariant(
    id="no-domain-leak",
    title="No domain leak",
    severity=Severity.ERROR,
    scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
    rule="Rule",
    rationale="Rationale",
    violating_examples="Bad",
    acceptable_examples="Good",
)


# ---------------------------------------------------------------------------
# v2 marker
# ---------------------------------------------------------------------------
class TestV2Marker:
    def test_marker_prefix_is_v2(self) -> None:
        assert MARKER_PREFIX.startswith("<!-- invariant-guardian:v2:")

    def test_rendered_comment_has_v2_marker(self) -> None:
        assessment = Assessment(
            status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS,
            coverage=Coverage(),
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)
        assert f"<!-- invariant-guardian:v2:{key} -->" in comment
        # Old v1 marker must not appear
        assert "<!-- invariant-guardian:" not in comment.replace(
            "<!-- invariant-guardian:v2:", ""
        )


# ---------------------------------------------------------------------------
# Coverage rendering
# ---------------------------------------------------------------------------
class TestCoverageRendering:
    def test_incomplete_shows_coverage_counts(self) -> None:
        assessment = Assessment(
            status=AssessmentStatus.INCOMPLETE,
            coverage=Coverage(
                evaluated_files=["src/Foo.java"],
                skipped_files=[
                    CoverageGap(file="src/Bar.java", reason="excluded by scope"),
                ],
            ),
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)

        assert "1 evaluated" in comment.lower() or "1 file(s) evaluated" in comment.lower()
        assert "1 skipped" in comment.lower() or "1 file(s) skipped" in comment.lower()

    def test_incomplete_with_provider_failure_warning(self) -> None:
        assessment = Assessment(
            status=AssessmentStatus.INCOMPLETE,
            coverage=Coverage(context_truncated=True),
            warnings=[
                SafeWarning(
                    category="provider_failure",
                    message="AI judgment was unavailable (provider_unavailable).",
                ),
            ],
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)

        assert "provider_unavailable" in comment.lower()
        # Never render raw exception text
        assert "traceback" not in comment.lower()

    def test_clean_shows_evaluated_count(self) -> None:
        assessment = Assessment(
            status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS,
            coverage=Coverage(evaluated_files=["src/Foo.java", "src/Bar.java"]),
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)
        assert "2 evaluated" in comment.lower() or "2 file(s) evaluated" in comment.lower()

    def test_confirmed_violations_with_candidates(self) -> None:
        assessment = Assessment(
            status=AssessmentStatus.CONFIRMED_VIOLATIONS,
            coverage=Coverage(evaluated_files=["src/Bad.java"]),
            candidates=[
                CandidateFinding(
                    invariant_id="no-domain-leak",
                    file="src/Bad.java",
                    start_line=10,
                    end_line=10,
                    pattern="public boundary",
                    evidence="public OrderEntity get()",
                    confidence="medium",
                ),
            ],
            violations=[
                Violation(
                    invariant_id="no-domain-leak",
                    file="src/Bad.java",
                    start_line=10,
                    end_line=10,
                    pattern="public boundary",
                    evidence="public OrderEntity get()",
                    confidence="medium",
                    why_it_matters="Entity leaks.",
                    suggested_direction="Use DTO.",
                ),
            ],
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)
        assert "confirmed" in comment.lower()
        assert "src/Bad.java" in comment
        assert "1 evaluated" in comment.lower() or "1 file(s) evaluated" in comment.lower()

    def test_no_confirmed_has_advisory(self) -> None:
        assessment = Assessment(
            status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS,
            coverage=Coverage(),
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)
        assert "human review" in comment.lower()

    def test_untrusted_content_is_markdown_escaped(self) -> None:
        """Evidence, provider output, and warnings must not render as
        active Markdown — they are untrusted input."""
        violation = Violation(
            invariant_id="no-domain-leak",
            file="src/Bad.java",
            start_line=10,
            end_line=10,
            pattern="public boundary",
            evidence="![img](https://evil.com/x.png) `code`",
            confidence="medium",
            why_it_matters="## Fake heading\n[click](https://phish.com)",
            suggested_direction="**bold** _italic_",
        )
        assessment = Assessment(
            status=AssessmentStatus.CONFIRMED_VIOLATIONS,
            coverage=Coverage(evaluated_files=["src/Bad.java"]),
            candidates=[
                CandidateFinding(
                    invariant_id="no-domain-leak",
                    file="src/Bad.java",
                    start_line=10,
                    end_line=10,
                    pattern="public boundary",
                    evidence="![img](https://evil.com/x.png) `code`",
                    confidence="medium",
                ),
            ],
            violations=[violation],
            warnings=[
                SafeWarning(
                    category="provider_failure",
                    message="[link](https://evil.com) and **bold**",
                ),
            ],
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)

        # These active Markdown patterns must be neutralized
        assert "![" not in comment, (
            f"Image syntax leaked: {comment}"
        )
        # Link text bracket must be escaped — `[click](url)` becomes
        # `\[click\](url)`.  An escaped `\]` breaks the link syntax.
        assert "[click](" not in comment, (
            f"Untrusted link syntax leaked: {comment}"
        )
        assert "[link](" not in comment, (
            f"Untrusted link in warning leaked: {comment}"
        )
        # Markdown heading from provider output must not render
        assert "\n## Fake heading" not in comment, (
            f"Untrusted heading leaked: {comment}"
        )

    def test_incomplete_with_violations_shows_both(self) -> None:
        """When coverage is incomplete but confirmed violations exist,
        the comment must show both — the incomplete warning AND the
        confirmed violations."""
        violation = Violation(
            invariant_id="no-domain-leak",
            file="src/Bad.java",
            start_line=10,
            end_line=10,
            pattern="public boundary",
            evidence="public OrderEntity get()",
            confidence="medium",
            why_it_matters="Entity leaks.",
            suggested_direction="Use DTO.",
        )
        assessment = Assessment(
            status=AssessmentStatus.INCOMPLETE,
            coverage=Coverage(
                evaluated_files=["src/Good.java"],
                skipped_files=[
                    CoverageGap(file="src/Missing.java", reason="truncated patch"),
                ],
            ),
            candidates=[
                CandidateFinding(
                    invariant_id="no-domain-leak",
                    file="src/Bad.java",
                    start_line=10,
                    end_line=10,
                    pattern="public boundary",
                    evidence="public OrderEntity get()",
                    confidence="medium",
                ),
            ],
            violations=[violation],
        )
        key = fingerprint(assessment, "abc123")
        comment = render_comment(assessment, [INVARIANT], key)

        # Must show incomplete warning
        assert "incomplete" in comment.lower()
        # Must show the violation
        assert "Entity leaks" in comment
        assert "src/Bad.java" in comment
        assert "Use DTO" in comment
        # Must show coverage
        assert "1 evaluated" in comment.lower() or "1 file(s) evaluated" in comment.lower()


# ---------------------------------------------------------------------------
# Fingerprint — unchanged
# ---------------------------------------------------------------------------
def test_fingerprint_changes_when_assessment_changes() -> None:
    clean = Assessment(
        status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS, coverage=Coverage()
    )
    incomplete = Assessment(status=AssessmentStatus.INCOMPLETE, coverage=Coverage())
    assert fingerprint(clean, "sha") != fingerprint(incomplete, "sha")
