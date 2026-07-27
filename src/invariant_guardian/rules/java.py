"""Java candidate detection — regex fallback and AST-based primary detection.

Phase 1 regex detectors are preserved for backward compatibility.
Phase 2 AST-based detectors use tree-sitter for structural analysis
without compiling or executing target-repository source.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from invariant_guardian.domain.models import CandidateFinding
from invariant_guardian.rules.java_ast import (
    detect_domain_leak_candidates,
    detect_monitoring_candidates,
)

TEMPORARY_MONITORING_ID = "no-temporary-monitoring"
DOMAIN_LEAK_ID = "no-domain-leak"

# ---------------------------------------------------------------------------
# Regex-based patterns (Phase 1 — preserved as fallback)
# ---------------------------------------------------------------------------

_MONITORING_PATTERNS = {
    "scheduled work": re.compile(r"@Scheduled|ScheduledExecutorService"),
    "wait retry": re.compile(r"Thread\.sleep|TimeUnit\.[A-Z_]+\.sleep"),
    "state polling": re.compile(r"while\s*\(|for\s*\(\s*;"),
}
_STATE_CHANGE = re.compile(r"\b(save|update|setStatus|transition|publishEvent|emit)\b")
_PUBLIC_BOUNDARY = re.compile(r"\bpublic\s+[A-Za-z0-9_<>?, ]+\s+[A-Za-z0-9_]+\s*\(")
_INTERNAL_TYPE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(Entity|Aggregate|PersistenceModel)\b")


# ---------------------------------------------------------------------------
# Legacy regex detector — kept for backward compatibility
# ---------------------------------------------------------------------------


def detect_candidates(diff: str, enabled_ids: Iterable[str]) -> list[CandidateFinding]:
    """Regex-based candidate detection (Phase 1 — preserved for backward compat).

    AST-based detection via :func:`detect_candidates_from_source` is preferred
    for new callers.
    """
    enabled = set(enabled_ids)
    findings: list[CandidateFinding] = []
    for path, line_number, line in _added_lines(diff):
        if not path.endswith(".java"):
            continue
        if TEMPORARY_MONITORING_ID in enabled:
            for name, pattern in _MONITORING_PATTERNS.items():
                if pattern.search(line) and _STATE_CHANGE.search(diff):
                    findings.append(
                        CandidateFinding(
                            invariant_id=TEMPORARY_MONITORING_ID,
                            file=path,
                            start_line=line_number,
                            end_line=line_number,
                            pattern=name,
                            evidence=line.strip(),
                            confidence="medium",
                        )
                    )
                    break
        if (
            DOMAIN_LEAK_ID in enabled
            and _PUBLIC_BOUNDARY.search(line)
            and (type_match := _INTERNAL_TYPE.search(line))
        ):
            findings.append(
                CandidateFinding(
                    invariant_id=DOMAIN_LEAK_ID,
                    file=path,
                    start_line=line_number,
                    end_line=line_number,
                    pattern="public boundary exposes likely internal type",
                    evidence=f"{line.strip()} (matched {type_match.group(0)})",
                    confidence="medium",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# AST-based primary detector — Phase 2
# ---------------------------------------------------------------------------


def detect_candidates_from_source(
    source: str,
    file_path: str,
    changed_lines: set[int],
    enabled_ids: Iterable[str],
) -> list[CandidateFinding]:
    """AST-based candidate detection using tree-sitter Java parsing.

    This is the preferred detector for Phase 2.  It parses *source* into a
    concrete syntax tree and walks the structure to find architecture-significant
    patterns — no regex-based false positives from naming coincidences.
    """
    enabled = set(enabled_ids)
    findings: list[CandidateFinding] = []

    if TEMPORARY_MONITORING_ID in enabled:
        for raw in detect_monitoring_candidates(source, file_path, changed_lines):
            findings.append(CandidateFinding(
                invariant_id=raw["invariant_id"],
                file=raw["file"],
                start_line=raw["start_line"],
                end_line=raw["end_line"],
                pattern=raw["pattern"],
                evidence=raw["evidence"],
                confidence=raw["confidence"],
            ))

    if DOMAIN_LEAK_ID in enabled:
        for raw in detect_domain_leak_candidates(source, file_path, changed_lines):
            findings.append(CandidateFinding(
                invariant_id=raw["invariant_id"],
                file=raw["file"],
                start_line=raw["start_line"],
                end_line=raw["end_line"],
                pattern=raw["pattern"],
                evidence=raw["evidence"],
                confidence=raw["confidence"],
            ))

    return findings


# ---------------------------------------------------------------------------
# Shared: unified diff line parsing (regex is fine for patch markers)
# ---------------------------------------------------------------------------


def _added_lines(diff: str) -> Iterable[tuple[str, int, str]]:
    path: str | None = None
    new_line: int | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line.removeprefix("+++ b/")
        elif line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
        elif path and new_line is not None:
            if line.startswith("+") and not line.startswith("+++"):
                yield path, new_line, line[1:]
                new_line += 1
            elif line.startswith(" "):
                new_line += 1


def extract_changed_lines_from_patch(patch: str) -> set[int]:
    """Return the line numbers of added/changed lines from a unified diff patch.

    This uses regex for patch markers only — structural detection is done via AST.
    """
    changed: set[int] = set()
    new_line: int | None = None
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
        elif new_line is not None:
            if line.startswith("+") and not line.startswith("+++"):
                changed.add(new_line)
                new_line += 1
            elif line.startswith(" "):
                new_line += 1
    return changed


def reconstruct_source_from_patch(patch: str) -> str:
    """Reconstruct a best-effort Java source snippet from a unified diff patch.

    Only context lines (`` `` prefix) and added lines (``+`` prefix) are
    included — removed lines are omitted to produce the *new* version of the
    code.  This is sufficient for tree-sitter to parse method signatures,
    annotations, and local structure.
    """
    lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++") or line.startswith(" "):
            lines.append(line[1:])
        # Skip --- / +++ headers, @@ hunk headers, and removed lines
    return "\n".join(lines)
