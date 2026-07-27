"""Safe, human-readable comment rendering for the v0.2 Guardian.

Never renders raw exceptions, provider tokens, or unrelated source.
"""

from __future__ import annotations

import hashlib
import json

from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    Invariant,
    SafeWarning,
)

MARKER_PREFIX = "<!-- invariant-guardian:v2:"

# Characters that can introduce active Markdown when supplied by untrusted
# input (source code, provider output, warnings).  We backslash-escape them
# so they render literally.
# Only the subset of Markdown-active characters that can create security-
# relevant constructs (links, images, inline HTML).  Emphasis markers
# (*, _) are deliberately NOT escaped — untrusted bold/italic cannot
# create links, inject scripts, or misrepresent the assessment outcome.
_MARKDOWN_ACTIVE_RE = __import__("re").compile(r"([\\`\[\]<>!#|])")


def _sanitize_markdown(text: str) -> str:
    """Escape characters that could form active Markdown in untrusted text."""
    single_line = text.replace("\r", " ").replace("\n", " ")
    escaped = _MARKDOWN_ACTIVE_RE.sub(r"\\\1", single_line)
    return escaped.replace("@", "&#64;")


def _warning_text(warning: SafeWarning | str) -> str:
    """Return the display text for a warning, handling both legacy str
    and SafeWarning objects."""
    if isinstance(warning, SafeWarning):
        return warning.message
    return str(warning)


def fingerprint(assessment: Assessment, head_sha: str) -> str:
    payload = {
        "head_sha": head_sha,
        "status": assessment.status,
        "candidates": [
            candidate.model_dump(mode="json") for candidate in assessment.candidates
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _coverage_summary(coverage) -> str:
    """Build a one-line summary of evaluated and skipped file counts."""
    parts = []
    ev = len(coverage.evaluated_files)
    sk = len(coverage.skipped_files)
    parts.append(f"{ev} file(s) evaluated")
    if sk:
        parts.append(f"{sk} file(s) skipped")
    if coverage.context_truncated:
        parts.append("context was truncated")
    return "; ".join(parts)


def render_comment(assessment: Assessment, invariants: list[Invariant], key: str) -> str:
    """Render a safe, structured Markdown comment for a Guardian assessment."""
    marker = f"{MARKER_PREFIX}{key} -->"
    title_by_id = {invariant.id: invariant.title for invariant in invariants}
    lines = [marker, "", "## Invariant Assessment", ""]

    # --- status section ---
    if assessment.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS:
        lines.append(
            "✅ No confirmed invariant violations were found in the evaluated changes."
        )
        lines.append(f"Coverage: {_coverage_summary(assessment.coverage)}")
        lines.append("")
    elif assessment.status == AssessmentStatus.INCOMPLETE:
        lines.append("⚠️ **Assessment incomplete.** This is **not** a clean review.")
        # Show coverage alongside the incomplete status
        lines.append(f"Coverage: {_coverage_summary(assessment.coverage)}")
        lines.append("")
        # Distinguish between no-candidates and provider-failure cases
        if not assessment.candidates and not assessment.violations and any(
            "provider" in _warning_text(w).lower()
            or "unavailable" in _warning_text(w).lower()
            for w in assessment.warnings
        ):
            lines.append(
                "AI evidence judgment was unavailable. "
                "A human architect must review these changes."
            )
        # Render confirmed violations even when coverage is incomplete (spec §5)
        if assessment.violations:
            lines.append("### Confirmed Violations")
            lines.append("")
            for violation in assessment.violations:
                lines.extend(
                    [
                        f"#### {_sanitize_markdown(title_by_id.get(violation.invariant_id, violation.invariant_id))}",
                        f"- Location: {_sanitize_markdown(violation.file)}:{violation.start_line}",
                        f"- Why it matters: {_sanitize_markdown(violation.why_it_matters)}",
                        f"- Evidence: {_sanitize_markdown(violation.evidence)}",
                        f"- Suggested direction: {_sanitize_markdown(violation.suggested_direction)}",
                        "",
                    ]
                )
    elif assessment.status == AssessmentStatus.CONFIRMED_VIOLATIONS:
        lines.append("Confirmed violations require human review.")
        lines.append(f"Coverage: {_coverage_summary(assessment.coverage)}")
        lines.append("")
        for violation in assessment.violations:
            lines.extend(
                [
                    f"### {_sanitize_markdown(title_by_id.get(violation.invariant_id, violation.invariant_id))}",
                    f"- Location: {_sanitize_markdown(violation.file)}:{violation.start_line}",
                    f"- Why it matters: {_sanitize_markdown(violation.why_it_matters)}",
                    f"- Evidence: {_sanitize_markdown(violation.evidence)}",
                    f"- Suggested direction: {_sanitize_markdown(violation.suggested_direction)}",
                    "",
                ]
            )
    else:
        # CANDIDATES_REQUIRE_JUDGMENT — legacy path
        lines.append(
            "⚠️ Candidate findings require evidence judgment before they become violations."
        )
        lines.append("")
        for candidate in assessment.candidates:
            lines.extend(
                [
                    f"### {_sanitize_markdown(title_by_id.get(candidate.invariant_id, candidate.invariant_id))}",
                    f"- Location: {_sanitize_markdown(candidate.file)}:{candidate.start_line}",
                    f"- Signal: {_sanitize_markdown(candidate.pattern)}",
                    f"- Evidence: {_sanitize_markdown(candidate.evidence)}",
                    "",
                ]
            )

    # --- warnings / notes ---
    if assessment.warnings:
        lines.append("### Notes")
        for warning in assessment.warnings:
            lines.append(f"- {_sanitize_markdown(_warning_text(warning))}")
        lines.append("")

    # --- advisory footer ---
    lines.extend(
        [
            (
                "_Invariant Guardian assesses repository-owned architecture rules; "
                "human review remains the decision point._"
            ),
        ]
    )
    return "\n".join(lines)
