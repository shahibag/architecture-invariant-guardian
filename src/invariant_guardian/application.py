from __future__ import annotations

from pathlib import Path

from invariant_guardian.domain.models import Assessment, AssessmentStatus
from invariant_guardian.invariants import load_invariants
from invariant_guardian.rules.java import detect_candidates


def assess_diff(invariant_directory: Path, diff: str) -> Assessment:
    invariants, warnings = load_invariants(invariant_directory)
    if not invariants:
        return Assessment(
            status=AssessmentStatus.INCOMPLETE,
            warnings=warnings or ["no valid invariant files found"],
        )
    candidates = detect_candidates(diff, (invariant.id for invariant in invariants))
    return Assessment(
        status=(
            AssessmentStatus.CANDIDATES_REQUIRE_JUDGMENT
            if candidates
            else AssessmentStatus.NO_CONFIRMED_VIOLATIONS
        ),
        candidates=candidates,
        warnings=warnings,
    )

