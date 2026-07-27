from __future__ import annotations

from pathlib import Path

from invariant_guardian.context import build_coverage, is_in_scope, normalize_path
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    ChangedFile,
    Coverage,
    CoverageGap,
    Invariant,
    ReviewRequest,
    SafeWarning,
)
from invariant_guardian.invariants import load_invariants
from invariant_guardian.rules.java import detect_candidates


class ReviewEngine:
    """Orchestrates the full advisory assessment from a :class:`ReviewRequest`.

    The engine owns scope enforcement, candidate detection, coverage
    tracking, and status precedence.  It delegates provider judgment to
    an injected ``LLMJudge`` (optional in Commit 1; wired in Commit 2).
    """

    def assess(self, request: ReviewRequest) -> Assessment:
        invariants = request.invariants
        changed_files = request.changed_files

        # --- coverage -------------------------------------------------------
        coverage = build_coverage(invariants, changed_files)

        # --- warnings from coverage gaps ------------------------------------
        warnings: list[SafeWarning] = []
        if coverage.skipped_files:
            warnings.append(
                SafeWarning(
                    category="coverage_gap",
                    message=(
                        f"{len(coverage.skipped_files)} file(s) could not be "
                        f"evaluated: {', '.join(g.file for g in coverage.skipped_files[:5])}"
                        f"{'...' if len(coverage.skipped_files) > 5 else ''}"
                    ),
                )
            )

        # --- detect candidates from in-scope, evaluable files ---------------
        enabled_ids = {inv.id for inv in invariants}
        candidates = []
        for cf in changed_files:
            norm = normalize_path(cf.path)
            if not any(is_in_scope(norm, inv) for inv in invariants):
                continue
            if cf.status == "removed":
                continue
            if cf.patch is None or not cf.patch_complete:
                continue
            patch_len = len(cf.patch.encode("utf-8"))
            from invariant_guardian.context import MAX_PATCH_BYTES

            if patch_len > MAX_PATCH_BYTES:
                continue
            # Use existing regex-based detection on per-file patches
            candidates.extend(detect_candidates(cf.patch, enabled_ids))

        # Apply candidate count limit
        if len(candidates) > 25:  # MAX_CANDIDATE_COUNT
            warnings.append(
                SafeWarning(
                    category="budget",
                    message=f"Candidate count capped at 25 (found {len(candidates)}).",
                )
            )
            candidates = candidates[:25]
            coverage.context_truncated = True

        # --- status precedence (spec §5) ------------------------------------
        # 1. INCOMPLETE if any in-scope Java change cannot be evaluated
        if coverage.skipped_files or coverage.context_truncated:
            status = AssessmentStatus.INCOMPLETE
        elif candidates:
            # No judge yet — candidates require judgment → INCOMPLETE
            status = AssessmentStatus.INCOMPLETE
            warnings.append(
                SafeWarning(
                    category="judge_unavailable",
                    message="AI evidence judgment was not available for this assessment.",
                )
            )
        else:
            status = AssessmentStatus.NO_CONFIRMED_VIOLATIONS

        return Assessment(
            status=status,
            candidates=candidates,
            coverage=coverage,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Backward-compatible assess_diff (will delegate to ReviewEngine.assess in
# a future refactor — kept working for now).
# ---------------------------------------------------------------------------


def assess_diff(invariant_directory: Path, diff: str) -> Assessment:
    """Legacy entry-point preserved for existing callers.

    Converts the flat diff into a :class:`ReviewRequest` and delegates to
    :class:`ReviewEngine`.  Coverage is now mandatory on every assessment.
    """
    invariants, load_warnings = load_invariants(invariant_directory)

    # Convert legacy str warnings to SafeWarning
    warnings: list[SafeWarning] = [
        SafeWarning(category="load", message=w) for w in (load_warnings or [])
    ]

    if not invariants:
        return Assessment(
            status=AssessmentStatus.INCOMPLETE,
            coverage=Coverage(),
            warnings=warnings or [SafeWarning(category="load", message="no valid invariant files found")],
        )

    # Convert diff to changed-file records for the engine
    changed_files = _diff_to_changed_files(diff)

    request = ReviewRequest(
        base_sha="unknown",
        head_sha="unknown",
        invariants=invariants,
        changed_files=changed_files,
    )
    engine = ReviewEngine()
    assessment = engine.assess(request)

    # Backward compat: the legacy assess_diff did not have a judge, so it
    # returned CANDIDATES_REQUIRE_JUDGMENT when candidates were found.
    # Preserve that behaviour while the transition to ReviewEngine.assess
    # is in progress.
    status = assessment.status
    if (
        status == AssessmentStatus.INCOMPLETE
        and assessment.candidates
        and not assessment.coverage.skipped_files
        and not assessment.coverage.context_truncated
    ):
        status = AssessmentStatus.CANDIDATES_REQUIRE_JUDGMENT

    # Merge load-time warnings
    all_warnings = list(warnings) + list(assessment.warnings)
    return Assessment(
        status=status,
        candidates=assessment.candidates,
        violations=assessment.violations,
        coverage=assessment.coverage,
        warnings=all_warnings,
    )


def _diff_to_changed_files(diff: str) -> list[ChangedFile]:
    """Crude conversion of a unified diff into :class:`ChangedFile` records.

    This is a bridge for the legacy ``assess_diff`` entry-point; the real
    GitHub adapter uses the files endpoint directly.
    """
    import re

    files: dict[str, list[str]] = {}
    current_path: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_path = line.removeprefix("+++ b/")
            files.setdefault(current_path, [])
            # Include the +++ b/ header so detect_candidates can still parse
            # the per-file unified diff.
            files[current_path].append(line)
        elif current_path is not None:
            files[current_path].append(line)

    result: list[ChangedFile] = []
    for path, lines in files.items():
        patch = "\n".join(lines)
        result.append(
            ChangedFile(
                path=path,
                status="modified",
                patch=patch if patch.strip() else None,
                patch_complete=True,
            )
        )
    return result
