from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    CandidateFinding,
    Coverage,
    Invariant,
    InvariantScope,
    Severity,
)
from invariant_guardian.rendering.comment import fingerprint, render_comment


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


def test_rendered_comment_has_stable_marker_and_candidate_evidence() -> None:
    assessment = Assessment(
        status=AssessmentStatus.CANDIDATES_REQUIRE_JUDGMENT,
        coverage=Coverage(evaluated_files=["src/OrderController.java"]),
        candidates=[
            CandidateFinding(
                invariant_id="no-domain-leak",
                file="src/OrderController.java",
                start_line=9,
                end_line=9,
                pattern="public boundary",
                evidence="public OrderEntity get()",
                confidence="medium",
            )
        ],
    )

    key = fingerprint(assessment, "abc123")
    comment = render_comment(assessment, [INVARIANT], key)

    assert f"<!-- invariant-guardian:{key} -->" in comment
    assert "src/OrderController.java:9" in comment
    assert "Candidate findings require evidence judgment" in comment


def test_fingerprint_changes_when_assessment_changes() -> None:
    clean = Assessment(status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS, coverage=Coverage())
    incomplete = Assessment(status=AssessmentStatus.INCOMPLETE, coverage=Coverage())

    assert fingerprint(clean, "sha") != fingerprint(incomplete, "sha")
