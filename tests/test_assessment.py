from pathlib import Path

from invariant_guardian.application import assess_diff
from invariant_guardian.domain.models import AssessmentStatus

FIXTURES = Path(__file__).parent / "fixtures"


def assess(name: str):
    return assess_diff(
        FIXTURES / "invariants",
        (FIXTURES / name).read_text(encoding="utf-8"),
    )


def test_flags_temporary_monitoring_candidate_with_state_change() -> None:
    assessment = assess("temporary_monitoring.diff")

    assert assessment.status == AssessmentStatus.CANDIDATES_REQUIRE_JUDGMENT
    assert assessment.candidates[0].invariant_id == "no-temporary-monitoring"
    # @Scheduled annotation is on new-file line 5 (hunk starts at +2, +3 lines of context=5)
    assert assessment.candidates[0].start_line == 5


def test_flags_public_entity_return_type() -> None:
    assessment = assess("domain_leak.diff")

    assert assessment.status == AssessmentStatus.CANDIDATES_REQUIRE_JUDGMENT
    assert assessment.candidates[0].invariant_id == "no-domain-leak"


def test_returns_clean_assessment_for_dto_response() -> None:
    assessment = assess("clean.diff")

    assert assessment.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS
    assert assessment.candidates == []
