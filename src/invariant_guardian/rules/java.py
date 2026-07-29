"""Java candidate detection — regex fallback and AST-based primary detection.

Phase 1 regex detectors are preserved for backward compatibility.
Phase 2 AST-based detectors use tree-sitter for structural analysis
without compiling or executing target-repository source.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from invariant_guardian.domain.models import CandidateFinding
from invariant_guardian.rules.java_ast import (
    detect_domain_leak_candidates,
    detect_monitoring_candidates,
    parse_java_source,
)

TEMPORARY_MONITORING_ID = "no-temporary-monitoring"
DOMAIN_LEAK_ID = "no-domain-leak"

# Explicit capability registry for v0.2. Only these IDs have detectors.
SUPPORTED_INVARIANT_IDS: frozenset[str] = frozenset(
    {TEMPORARY_MONITORING_ID, DOMAIN_LEAK_ID}
)

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

    Domain-leak regex patterns are intentionally excluded — regex-only type
    matching must never create a confirmable candidate without AST boundary
    and bounded declaration evidence (spec §8).
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
    return findings


# ---------------------------------------------------------------------------
# AST-based primary detector — Phase 2
# ---------------------------------------------------------------------------


def detect_candidates_from_source(
    source: str,
    file_path: str,
    changed_lines: set[int],
    enabled_ids: Iterable[str],
    source_to_new_line_map: dict[int, int] | None = None,
    source_reader: Callable[[str], str | None] | None = None,
) -> list[CandidateFinding]:
    """AST-based candidate detection using tree-sitter Java parsing.

    This is the preferred detector for Phase 2.  It parses *source* into a
    concrete syntax tree and walks the structure to find architecture-significant
    patterns — no regex-based false positives from naming coincidences.

    When *source_to_new_line_map* is provided, *changed_lines* (new-file
    coordinates) are translated to source-relative line numbers before
    intersecting with AST-reported method ranges.

    *source_reader* is an optional ``(type_name: str) -> str | None``
    callable used to resolve type declarations for naming-convention
    evidence.
    """
    enabled = set(enabled_ids)
    findings: list[CandidateFinding] = []

    # A patch fragment that tree-sitter can recover as loose top-level nodes
    # is not a complete structural analysis unit.  Require an enclosing Java
    # type declaration; callers convert this failure into a coverage gap.
    tree = parse_java_source(source)
    declaration_types = {
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "annotation_type_declaration",
    }
    if not any(child.type in declaration_types for child in tree.root_node.named_children):
        raise ValueError("Java source lacks a complete top-level declaration")

    # Translate changed_lines from new-file to source-relative coordinates
    # when a line map is available.
    source_changed_lines: set[int] = set()
    if source_to_new_line_map and changed_lines:
        # Build inverse: new_file_line → source_line
        new_to_source: dict[int, int] = {}
        for src_line, new_line in source_to_new_line_map.items():
            if new_line not in new_to_source:
                new_to_source[new_line] = src_line
        for nl in changed_lines:
            if nl in new_to_source:
                source_changed_lines.add(new_to_source[nl])
        if not source_changed_lines:
            # No changed lines mapped to reconstructed source — nothing to check
            return findings
    else:
        source_changed_lines = changed_lines

    if TEMPORARY_MONITORING_ID in enabled:
        for raw in detect_monitoring_candidates(source, file_path, source_changed_lines):
            findings.append(CandidateFinding(
                invariant_id=raw["invariant_id"],
                file=raw["file"],
                start_line=raw["start_line"],
                end_line=raw["end_line"],
                pattern=raw["pattern"],
                evidence=raw["evidence"],
                confidence=raw["confidence"],
                related_evidence=raw.get("related_evidence"),
            ))

    if DOMAIN_LEAK_ID in enabled:
        for raw in detect_domain_leak_candidates(
            source, file_path, source_changed_lines, source_reader=source_reader,
        ):
            findings.append(CandidateFinding(
                invariant_id=raw["invariant_id"],
                file=raw["file"],
                start_line=raw["start_line"],
                end_line=raw["end_line"],
                pattern=raw["pattern"],
                evidence=raw["evidence"],
                confidence=raw["confidence"],
                related_evidence=raw.get("related_evidence"),
            ))

    # --- Map emitted source-relative coordinates back to new-file lines ---
    # Detectors report line numbers in reconstructed-source coordinates
    # (1-based from the start of the contiguous source).  The downstream
    # engine and judge must operate on repository-relative new-file line
    # numbers.  Without this reverse map, candidates at large offsets
    # report phantom lines that don't exist at the repository location
    # (spec §4, Phase 2 acceptance lines 438–439).
    if source_to_new_line_map:
        for f in findings:
            if f.start_line in source_to_new_line_map:
                f.start_line = source_to_new_line_map[f.start_line]
            if f.end_line in source_to_new_line_map:
                f.end_line = source_to_new_line_map[f.end_line]

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


def reconstruct_source_from_patch(patch: str) -> tuple[str, dict[int, int]]:
    """Reconstruct a best-effort Java source snippet from a unified diff patch.

    Only context lines (`` `` prefix) and added lines (``+`` prefix) are
    included — removed lines are omitted to produce the *new* version of the
    code.  This is sufficient for tree-sitter to parse method signatures,
    annotations, and local structure.

    Raises :class:`ValueError` when the patch contains disjoint hunks whose
    gap exceeds safe structural integrity — lines between hunks are unknown
    and must not be silently elided.

    Returns ``(source, source_to_new_line_map)`` where the map translates
    each reconstructed-source line number (1-based) to the corresponding
    new-file line number.  This is essential for correctly intersecting
    AST-reported line ranges with changed-line sets that use new-file
    coordinates.
    """
    source_lines: list[str] = []
    source_to_new: dict[int, int] = {}
    new_line: int | None = None
    previous_hunk_end: int | None = None
    hunk_start: int | None = None

    for line in patch.splitlines():
        if line.startswith("@@"):
            # Close the preceding hunk before comparing the next header.
            if new_line is not None and new_line > 1:
                previous_hunk_end = new_line - 1
            match = re.search(r"\+(\d+)", line)
            hunk_start = int(match.group(1)) if match else None
            # --- Disjoint-hunk detection (P0 finding 1) -------------------
            # When two hunks are separated by a gap of unknown lines, the
            # reconstructed source cannot guarantee structural integrity.
            # Silently joining them creates Frankenstein sources where
            # tree-sitter fabricates relationships across missing context.
            if (
                previous_hunk_end is not None
                and hunk_start is not None
                and hunk_start > previous_hunk_end + 1
            ):
                raise ValueError(
                    f"Disjoint hunks: gap between new-file lines "
                    f"{previous_hunk_end} and {hunk_start} — "
                    f"structural integrity cannot be guaranteed"
                )
            new_line = hunk_start
            continue
        if (
            line.startswith("+") and not line.startswith("+++")
            or line.startswith(" ")
        ) and new_line is not None:
            source_lines.append(line[1:])
            source_to_new[len(source_lines)] = new_line
            new_line += 1
        # Skip --- / +++ headers, removed lines, and lines before any hunk

    # Record last line of the final hunk for callers that check disjointness
    if new_line is not None and new_line > 1:
        previous_hunk_end = new_line - 1

    return "\n".join(source_lines), source_to_new
