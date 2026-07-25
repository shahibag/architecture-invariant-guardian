from __future__ import annotations

import hashlib
import json

from invariant_guardian.domain.models import Assessment, AssessmentStatus, Invariant


MARKER_PREFIX = "<!-- invariant-guardian:"


def fingerprint(assessment: Assessment, head_sha: str) -> str:
    payload = {
        "head_sha": head_sha,
        "status": assessment.status,
        "candidates": [
            candidate.model_dump(mode="json") for candidate in assessment.candidates
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def render_comment(assessment: Assessment, invariants: list[Invariant], key: str) -> str:
    marker = f"{MARKER_PREFIX}{key} -->"
    title_by_id = {invariant.id: invariant.title for invariant in invariants}
    lines = [marker, "## Invariant Assessment", ""]
    if assessment.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS:
        lines.append("No confirmed invariant violations were found in the evaluated changes.")
    elif assessment.status == AssessmentStatus.INCOMPLETE:
        lines.append("⚠️ Assessment incomplete. This is not a clean review.")
    else:
        lines.extend(
            [
                "⚠️ Candidate findings require evidence judgment before they become violations.",
                "",
            ]
        )
        for candidate in assessment.candidates:
            lines.extend(
                [
                    f"### {title_by_id.get(candidate.invariant_id, candidate.invariant_id)}",
                    f"- Location: {candidate.file}:{candidate.start_line}",
                    f"- Signal: {candidate.pattern}",
                    f"- Evidence: {candidate.evidence}",
                    f"- Confidence: {candidate.confidence}",
                    "",
                ]
            )
    if assessment.warnings:
        lines.extend(["### Notes", *[f"- {warning}" for warning in assessment.warnings]])
    lines.extend(
        [
            "",
            "_Invariant Guardian assesses repository-owned architecture rules; human review remains the decision point._",
        ]
    )
    return "\n".join(lines)
