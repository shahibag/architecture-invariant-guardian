"""Scope enforcement, path normalisation, and fixed context budgets."""

from __future__ import annotations

import fnmatch as _fnmatch
import os
import re

from invariant_guardian.domain.models import (
    ChangedFile,
    Coverage,
    CoverageGap,
    Invariant,
)

# ---------------------------------------------------------------------------
# Fixed context budgets (spec §7)
# ---------------------------------------------------------------------------

MAX_CHANGED_FILES = 200
MAX_PATCH_BYTES = 200_000
MAX_CANDIDATE_COUNT = 25
MAX_SOURCE_BYTES_PER_FILE = 100_000
MAX_MODEL_CONTEXT_CHARS = 60_000
CONTEXT_LINES = 40


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------

def normalize_path(path: str) -> str:
    """Normalise a repository-relative POSIX path.

    Removes leading slashes, dot segments, and resolves ``..`` safely.
    """
    if not path:
        return ""
    # Strip leading ./ or /
    cleaned = path.lstrip("/")
    cleaned = cleaned.removeprefix("./")
    if not cleaned:
        return ""
    # Resolve .. segments via os.path.normpath, then force POSIX slashes
    cleaned = os.path.normpath(cleaned)
    return cleaned.replace("\\", "/")


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------

_LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "java": [".java"],
}


def _validate_include_paths(paths: list[str]) -> None:
    """Raise ValueError if any include_path glob is syntactically invalid.

    We use :func:`fnmatch.translate` as a lightweight validity check;
    a broken pattern raises ``re.error``.
    """
    for p in paths:
        try:
            re.compile(_fnmatch.translate(p))
        except re.error as exc:
            raise ValueError(f"invalid scope include_path {p!r}: {exc}") from exc


_ABSOLUTE_PATH_RE = re.compile(r"^(/[^/]+|[A-Za-z]:[/\\])")
_TRAVERSAL_RE = re.compile(r"(?:^|[/\\])\.\.[/\\]")


def is_in_scope(file_path: str, invariant: Invariant) -> bool:
    """Return True when *file_path* matches the invariant's language and path
    scope.

    The file is expected to already be normalised via :func:`normalize_path`.
    """
    # Reject absolute paths and path traversal
    if _ABSOLUTE_PATH_RE.match(file_path) or _TRAVERSAL_RE.search(file_path):
        return False

    # Validate the invariant's path patterns
    _validate_include_paths(invariant.scope.include_paths)

    # Language check
    extensions = _LANGUAGE_EXTENSIONS.get(
        invariant.scope.languages[0] if invariant.scope.languages else "", []
    )
    if not extensions:
        return False
    if not any(file_path.endswith(ext) for ext in extensions):
        return False

    # Path-scope check: at least one include_path glob must match
    for pattern in invariant.scope.include_paths:
        if _fnmatch.fnmatch(file_path, pattern):
            return True
    return False


# ---------------------------------------------------------------------------
# Coverage builder
# ---------------------------------------------------------------------------

def build_coverage(
    invariants: list[Invariant], changed_files: list[ChangedFile]
) -> Coverage:
    """Produce a :class:`Coverage` record for the given invariants and files.

    Files are classified as *evaluated* (in scope, patch present, not
    oversized), or *skipped* with a reason.
    """
    evaluated: list[str] = []
    skipped: list[CoverageGap] = []
    truncated = False

    # Truncate total file count
    if len(changed_files) > MAX_CHANGED_FILES:
        truncated = True
        changed_files = changed_files[:MAX_CHANGED_FILES]

    for cf in changed_files:
        norm = normalize_path(cf.path)

        # Check scope against any invariant
        in_any_scope = any(is_in_scope(norm, inv) for inv in invariants)
        if not in_any_scope:
            skipped.append(CoverageGap(file=norm, reason="excluded by scope"))
            continue

        if not cf.patch_complete:
            skipped.append(CoverageGap(file=norm, reason="truncated patch"))
            truncated = True
            continue

        patch_bytes = len(cf.patch.encode("utf-8")) if cf.patch else 0
        if patch_bytes > MAX_PATCH_BYTES:
            skipped.append(
                CoverageGap(
                    file=norm,
                    reason=f"patch exceeds {MAX_PATCH_BYTES}-byte limit ({patch_bytes} bytes)",
                )
            )
            truncated = True
            continue

        # Removed files are tracked but not evaluated for new violations
        if cf.status == "removed":
            evaluated.append(norm)
            continue

        evaluated.append(norm)

    return Coverage(
        evaluated_files=evaluated,
        skipped_files=skipped,
        context_truncated=truncated,
    )
