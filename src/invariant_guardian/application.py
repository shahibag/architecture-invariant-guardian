from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from invariant_guardian.context import (
    CONTEXT_LINES,
    MAX_CANDIDATE_COUNT,
    MAX_CHANGED_FILES,
    MAX_MODEL_CONTEXT_CHARS,
    MAX_PATCH_BYTES,
    build_coverage,
    is_in_scope,
    normalize_path,
)
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    CandidateFinding,
    ChangedFile,
    Coverage,
    JudgeCandidate,
    JudgeRequest,
    JudgeResult,
    ReviewRequest,
    SafeWarning,
)
from invariant_guardian.invariants import load_invariants
from invariant_guardian.prompt import judge_message_chars
from invariant_guardian.rules.java import (
    detect_candidates,
    detect_candidates_from_source,
    extract_changed_lines_from_patch,
    reconstruct_source_from_patch,
)

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
        evaluated_paths = set(coverage.evaluated_files)

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
        candidates: list[CandidateFinding] = []
        # Map file → patch for bounded context extraction
        file_patches: dict[str, str] = {}
        for cf in changed_files[:MAX_CHANGED_FILES]:
            try:
                norm = normalize_path(cf.path)
            except ValueError:
                continue
            # Determine which invariants actually include this file — scope
            # is enforced independently per invariant (spec §7).
            in_scope_ids = {
                inv.id for inv in invariants if is_in_scope(norm, inv)
            }
            if not in_scope_ids:
                continue
            # Coverage owns all fixed file/aggregate patch budgets. Never
            # analyze a file it excluded, even when its patch is otherwise
            # parseable.
            if norm not in evaluated_paths:
                continue
            if cf.status == "removed":
                continue
            if cf.patch is None or not cf.patch_complete:
                continue
            patch_len = len(cf.patch.encode("utf-8"))
            if patch_len > MAX_PATCH_BYTES:
                continue
            normalised = _normalize_patch(cf.patch, norm)
            file_patches[norm] = normalised
            # Phase 2: reconstruct Java source from the patch and use
            # AST-based detection for structural accuracy.
            # Phase 1 regex detection runs as a fallback when the patch
            # lacks enough context for AST parsing, or when AST errors.
            if norm.endswith(".java"):
                ast_findings: list[CandidateFinding] = []
                try:
                    source = reconstruct_source_from_patch(cf.patch)
                    changed_lines = extract_changed_lines_from_patch(cf.patch)
                    ast_findings = detect_candidates_from_source(
                        source, norm, changed_lines, in_scope_ids
                    )
                except Exception:  # noqa: BLE001 — AST must never crash the engine
                    ast_findings = []
                if ast_findings:
                    candidates.extend(ast_findings)
                else:
                    # Fall back to regex when AST yields nothing — the patch
                    # may lack enough context for structural detection.
                    candidates.extend(detect_candidates(normalised, in_scope_ids))
            else:
                candidates.extend(detect_candidates(normalised, in_scope_ids))

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
                context_hunk = _extract_bounded_context(patch, c.start_line) or c.evidence
                jc = JudgeCandidate(
                    index=i,
                    invariant_id=c.invariant_id,
                    invariant_text=invariant_text,
                    file=c.file,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    evidence=c.evidence,
                    context_hunk=context_hunk,
                )
                # Enforce MAX_MODEL_CONTEXT_CHARS: measure the serialised size
                # of all candidates accumulated so far.  If adding this
                # candidate would breach the ceiling, stop here.
                trial = [*judge_candidates, jc]
                trial_size = judge_message_chars(JudgeRequest(candidates=trial))
                if trial_size > MAX_MODEL_CONTEXT_CHARS:
                    if judge_candidates:
                        # Truncate — record the gap
                        warnings.append(
                            SafeWarning(
                                category="budget",
                                message=(
                                    f"Model context ceiling "
                                    f"({MAX_MODEL_CONTEXT_CHARS} chars) "
                                    f"reached; {len(candidates) - i} "
                                    f"candidate(s) excluded."
                                ),
                            )
                        )
                        coverage.context_truncated = True
                    else:
                        # Even the first candidate alone is too large
                        warnings.append(
                            SafeWarning(
                                category="budget",
                                message=(
                                    f"Single candidate exceeds model-context "
                                    f"ceiling ({MAX_MODEL_CONTEXT_CHARS} chars)."
                                ),
                            )
                        )
                        coverage.context_truncated = True
                    break
                judge_candidates.append(jc)

            if judge_candidates:
                judge_request = JudgeRequest(candidates=judge_candidates)
                try:
                    judge_result = judge.evaluate(judge_request)
                except Exception:  # noqa: BLE001 - provider boundary must never crash review
                    # Provider adapters are untrusted boundaries. Preserve a
                    # safe incomplete result without exposing exception text.
                    coverage.context_truncated = True
                    warnings.append(
                        SafeWarning(
                            category="provider_failure",
                            message="Provider judgment failed; human review is required.",
                        )
                    )
                    judge_result = None
                if not isinstance(judge_result, JudgeResult):
                    coverage.context_truncated = True
                    warnings.append(
                        SafeWarning(
                            category="provider_failure",
                            message="Provider returned an invalid judgment result.",
                        )
                    )
                    judge_result = None

                # --- v0.2 spec §9: validate every JudgeResult regardless of
                # provider implementation (not just OpenAI) -------------------
                if judge_result is not None:
                    validation_errors = _validate_judge_result(
                        judge_result, len(judge_candidates)
                    )
                    if validation_errors:
                        coverage.context_truncated = True
                        for err in validation_errors:
                            warnings.append(
                                SafeWarning(category="provider_failure", message=err)
                            )

                    provider_usage = judge_result.provider_usage

                    if judge_result.truncated or judge_result.errors:
                        coverage.context_truncated = True
                        warnings.append(
                            SafeWarning(
                                category="provider_failure",
                                message="Provider judgment did not complete safely.",
                            )
                        )

                    result_valid = not (
                        validation_errors
                        or judge_result.truncated
                        or judge_result.errors
                    )
                    if result_valid:
                        # Only a complete, validated decision set can create
                        # confirmed violations.
                        from invariant_guardian.domain.models import Violation

                        for d in judge_result.decisions:
                            if d.decision == "confirm":
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
# Patch normalisation — GitHub patches lack +++ b/<path> headers
# ---------------------------------------------------------------------------


def _normalize_patch(patch: str, path: str) -> str:
    """Ensure *patch* begins with a ``+++ b/<path>`` header.

    GitHub per-file patches from the REST API contain only ``@@`` hunk
    headers and body lines; ``_added_lines`` and ``_extract_bounded_context``
    both depend on the ``+++`` header to set the current file.
    """
    if patch.startswith(("+++ b/", "--- a/")):
        return patch
    return f"+++ b/{path}\n{patch}"


# ---------------------------------------------------------------------------
# Bounded context extraction
# ---------------------------------------------------------------------------

_CONTEXT_LINES = CONTEXT_LINES


def _extract_bounded_context(patch: str, target_line: int) -> str:
    """Extract a bounded diff hunk around *target_line* from *patch*.

    Returns at most the lines around the target plus ``_CONTEXT_LINES`` of
    surrounding context — never the full diff.  Hunk headers for hunks that
    are more than ``_CONTEXT_LINES`` away from the target are excluded.
    """
    import re

    selected: list[str] = []
    header: str | None = None
    hunk_lines: list[str] = []
    new_line: int | None = None
    max_body_lines = 2 * _CONTEXT_LINES + 1
    max_total_lines = max_body_lines + 1

    def _flush_hunk() -> None:
        nonlocal header, hunk_lines
        remaining = max_total_lines - len(selected)
        if header is not None and hunk_lines and remaining > 1:
            selected.append(header)
            selected.extend(hunk_lines[: remaining - 1])
        header = None
        hunk_lines = []

    for line in patch.splitlines():
        if line.startswith("@@"):
            _flush_hunk()
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
            header = line
            continue
        if new_line is None:
            continue

        if abs(new_line - target_line) <= _CONTEXT_LINES and len(hunk_lines) < max_body_lines:
            hunk_lines.append(line)

        if (line.startswith("+") and not line.startswith("+++")) or line.startswith(" "):
            new_line += 1

    _flush_hunk()
    return "\n".join(selected)


def _validate_judge_result(
    judge_result: JudgeResult, candidate_count: int
) -> list[str]:
    """Validate a :class:`JudgeResult` against the strict v0.2 contract.

    For *candidate_count* candidates the result must contain:
    - exactly *candidate_count* decisions;
    - every index from 0 through *candidate_count*-1 exactly once;
    - no unknown candidate index.

    Returns a (possibly empty) list of human-readable error descriptions.
    """
    errors: list[str] = []

    if len(judge_result.decisions) != candidate_count:
        errors.append(
            f"expected {candidate_count} decisions, "
            f"got {len(judge_result.decisions)}"
        )

    seen: set[int] = set()
    for d in judge_result.decisions:
        idx = d.candidate_index
        if idx < 0 or idx >= candidate_count:
            errors.append(f"unknown candidate index {idx}")
        if idx in seen:
            errors.append(f"duplicate candidate index {idx}")
        seen.add(idx)

    expected = set(range(candidate_count))
    missing = expected - seen
    if missing:
        errors.append(f"missing candidate indexes: {sorted(missing)}")

    return errors


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

    # P2.2: Invariant-load warnings force the assessment incomplete (spec §7).
    # A partial invariant load is a coverage gap — we cannot guarantee that
    # in-scope files were evaluated against the failed invariant.
    if warnings and not assessment.coverage.skipped_files:
        status = AssessmentStatus.INCOMPLETE

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
