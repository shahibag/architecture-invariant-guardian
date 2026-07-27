from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invariant_guardian.context import (
    CONTEXT_LINES,
    MAX_CANDIDATE_COUNT,
    MAX_PATCH_BYTES,
    build_coverage,
    is_in_scope,
    normalize_path,
)
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    ChangedFile,
    Coverage,
    JudgeCandidate,
    JudgeRequest,
    ReviewRequest,
    SafeWarning,
)
from invariant_guardian.invariants import load_invariants
from invariant_guardian.rules.java import detect_candidates

if TYPE_CHECKING:
    from invariant_guardian.ports import LLMJudge


class ReviewEngine:
    """Orchestrates the full advisory assessment from a :class:`ReviewRequest`.

    The engine owns scope enforcement, candidate detection, coverage
    tracking, and status precedence.  It delegates provider judgment to
    an injected :class:`~invariant_guardian.ports.LLMJudge`.
    """

    def assess(
        self, request: ReviewRequest, judge: LLMJudge | None = None
    ) -> Assessment:
        invariants = request.invariants
        changed_files = request.changed_files

        # --- no invariants → immediate INCOMPLETE ---------------------------
        if not invariants:
            return Assessment(
                status=AssessmentStatus.INCOMPLETE,
                coverage=Coverage(),
                warnings=[
                    SafeWarning(
                        category="load",
                        message="No invariants loaded — cannot assess changes.",
                    )
                ],
            )

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
        # Map file → patch for bounded context extraction
        file_patches: dict[str, str] = {}
        for cf in changed_files:
            norm = normalize_path(cf.path)
            if not any(is_in_scope(norm, inv) for inv in invariants):
                continue
            if cf.status == "removed":
                continue
            if cf.patch is None or not cf.patch_complete:
                continue
            patch_len = len(cf.patch.encode("utf-8"))
            if patch_len > MAX_PATCH_BYTES:
                continue
            file_patches[norm] = cf.patch
            # Use existing regex-based detection on per-file patches
            candidates.extend(detect_candidates(cf.patch, enabled_ids))

        # Apply candidate count limit
        if len(candidates) > MAX_CANDIDATE_COUNT:
            warnings.append(
                SafeWarning(
                    category="budget",
                    message=(
                        f"Candidate count capped at {MAX_CANDIDATE_COUNT} "
                        f"(found {len(candidates)})."
                    ),
                )
            )
            candidates = candidates[:MAX_CANDIDATE_COUNT]
            coverage.context_truncated = True

        # --- build provider usage / violations via judge --------------------
        provider_usage = None
        violations = []

        if judge is not None and candidates:
            # Build bounded JudgeRequest — no unbounded full diff
            invariant_map = {inv.id: inv for inv in invariants}
            judge_candidates: list[JudgeCandidate] = []
            for i, c in enumerate(candidates):
                inv = invariant_map.get(c.invariant_id)
                invariant_text = (
                    f"Rule: {inv.rule}\nRationale: {inv.rationale}"
                    if inv
                    else f"Rule: {c.invariant_id}"
                )
                patch = file_patches.get(c.file, "")
                context_hunk = _extract_bounded_context(patch, c.start_line)
                judge_candidates.append(
                    JudgeCandidate(
                        index=i,
                        invariant_id=c.invariant_id,
                        invariant_text=invariant_text,
                        file=c.file,
                        start_line=c.start_line,
                        end_line=c.end_line,
                        evidence=c.evidence,
                        context_hunk=context_hunk,
                    )
                )

            judge_request = JudgeRequest(candidates=judge_candidates)
            judge_result = judge.evaluate(judge_request)

            provider_usage = judge_result.provider_usage

            if judge_result.truncated or judge_result.errors:
                coverage.context_truncated = True
                for err in judge_result.errors:
                    warnings.append(
                        SafeWarning(category="provider_failure", message=err)
                    )

            # Convert confirmed decisions to violations
            from invariant_guardian.domain.models import Violation

            for d in judge_result.decisions:
                if d.decision == "confirm" and d.candidate_index < len(candidates):
                    c = candidates[d.candidate_index]
                    violations.append(
                        Violation(
                            **c.model_dump(),
                            why_it_matters=d.why_it_matters,
                            suggested_direction=d.suggested_direction,
                        )
                    )

        # --- status precedence (spec §5) ------------------------------------
        # INCOMPLETE when any in-scope change cannot be fully evaluated.
        # Confirmed violations + coverage gaps → assessment_incomplete with
        # violations still rendered.
        if coverage.skipped_files or coverage.context_truncated:
            status = AssessmentStatus.INCOMPLETE
        elif candidates and judge is None:
            status = AssessmentStatus.INCOMPLETE
            warnings.append(
                SafeWarning(
                    category="judge_unavailable",
                    message="AI evidence judgment was not available for this assessment.",
                )
            )
        elif violations:
            status = AssessmentStatus.CONFIRMED_VIOLATIONS
        elif candidates:
            # A present judge returned a complete exact decision set and
            # rejected every candidate. This is a completed clean assessment.
            status = AssessmentStatus.NO_CONFIRMED_VIOLATIONS
        else:
            status = AssessmentStatus.NO_CONFIRMED_VIOLATIONS

        return Assessment(
            status=status,
            candidates=candidates,
            violations=violations,
            coverage=coverage,
            provider_usage=provider_usage,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Bounded context extraction
# ---------------------------------------------------------------------------

_CONTEXT_LINES = CONTEXT_LINES


def _extract_bounded_context(patch: str, target_line: int) -> str:
    """Extract a bounded diff hunk around *target_line* from *patch*.

    Returns at most the lines around the target plus ``_CONTEXT_LINES`` of
    surrounding context — never the full diff.
    """
    lines: list[str] = []
    new_line: int | None = None

    for line in patch.splitlines():
        if line.startswith("@@"):
            import re

            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
            lines.append(line)
            continue
        if new_line is None:
            continue

        if abs(new_line - target_line) <= _CONTEXT_LINES:
            lines.append(line)

        if (
            line.startswith("+") and not line.startswith("+++")
        ) or line.startswith(" "):
            new_line += 1

    return "\n".join(lines) if lines else patch[:2000]


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
            warnings=warnings
            or [SafeWarning(category="load", message="no valid invariant files found")],
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
