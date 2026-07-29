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

# Phase 3 — Comment pagination bounds
# Conservative ceilings: GitHub defaults to 30 per page, max 100.
# 10 pages × 100 = 1 000 comments is far beyond any realistic PR.
MAX_COMMENT_PAGES = 10
MAX_COMMENTS = 1_000
MAX_COMMENT_BYTES = 1_000_000  # 1 MiB of JSON response body

# Phase 3 — Changed-file pagination bounds
# GitHub's /files endpoint returns 100 items per page by default.
# 20 pages × 100 = 2 000 files is well beyond any realistic PR.
MAX_CHANGED_FILE_PAGES = 20
MAX_CHANGED_FILE_BYTES = 5_000_000  # 5 MiB of JSON response body

# Phase 3 — HTTP response bounds
# GitHub REST API responses rarely exceed a few MiB.  10 MiB is a
# generous ceiling that still protects against runaway allocations.
MAX_RESPONSE_BYTES = 10_000_000  # 10 MiB
MAX_HTTP_RETRIES = 3
MAX_RETRY_DELAY = 10  # seconds

# Binary content detection — files containing null bytes or with high
# ratios of non-printable characters are rejected
_BINARY_THRESHOLD = 0.10  # reject when >10% of initial bytes are non-printable


# ---------------------------------------------------------------------------
# Safe source-file reading
# ---------------------------------------------------------------------------


def read_source_safely(
    raw_content: bytes | None,
    path: str,
    byte_cap: int = MAX_SOURCE_BYTES_PER_FILE,
) -> str | None:
    """Safely decode source content for structural analysis.

    Enforces:
    - *raw_content* must not be ``None`` (missing/unavailable)
    - Pre-decode byte cap at *byte_cap* — oversized content is REJECTED
    - Binary rejection (null bytes, high non-printable ratio)
    - Strict UTF-8 — invalid bytes are NEVER replaced with U+FFFD

    Returns decoded ``str``, or ``None`` when the content is missing,
    oversized, binary, or invalid UTF-8.  ``None`` here means the file
    is unavailable for structural analysis and must be recorded as a
    coverage gap.
    """
    if raw_content is None:
        return None

    # Pre-decode byte cap — oversized content is rejected, not truncated.
    # Truncation hides whether critical type information is present.
    if len(raw_content) > byte_cap:
        return None

    # Binary rejection: check for null bytes
    if b"\x00" in raw_content:
        return None

    # Binary rejection: check non-printable ratio in first 4 KiB
    sample = raw_content[:4096]
    if len(sample) > 0:
        non_printable = sum(
            1 for b in sample if b < 0x20 and b not in (0x09, 0x0A, 0x0D)
        )
        if non_printable / len(sample) > _BINARY_THRESHOLD:
            return None

    # Strict UTF-8 — never replace invalid bytes
    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        return None

    return text


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------

def normalize_path(path: str) -> str:
    """Normalise a repository-relative POSIX path.

    Removes leading slashes, dot segments, and resolves ``..`` safely.

    Raises ValueError for input that cannot be normalised to a safe
    repository-relative path (null bytes, traversal that escapes the
    repository root).
    """
    if "\x00" in path:
        raise ValueError(f"unsafe path {path!r}: null byte")

    if not path:
        return ""
    # Repository paths must be relative. Reject absolute paths before any
    # cleanup can accidentally turn them into apparently safe relative paths.
    if _ABSOLUTE_PATH_RE.match(path):
        raise ValueError(f"unsafe path {path!r}: absolute")
    # Strip a harmless leading ./ only.
    cleaned = path
    cleaned = cleaned.removeprefix("./")
    if not cleaned:
        return ""
    # Resolve .. segments via os.path.normpath, then force POSIX slashes
    cleaned = os.path.normpath(cleaned)
    # After normalisation a safe path must not start with .. (escape) or
    # be an absolute filesystem path.
    if cleaned.startswith("..") and (len(cleaned) == 2 or cleaned[2] in ("/", "\\")):
        raise ValueError(f"unsafe path {path!r}: traversal escapes repository root")
    if _ABSOLUTE_PATH_RE.match(cleaned):
        raise ValueError(f"unsafe path {path!r}: absolute")
    return cleaned.replace("\\", "/")


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------

_LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "java": [".java"],
}


_ABSOLUTE_PATH_RE = re.compile(r"^(/[^/]+|[A-Za-z]:[/\\])")
_TRAVERSAL_RE = re.compile(r"(?:^|[/\\])\.\.[/\\]")
_UNBALANCED_BRACKET_RE = re.compile(r"\[[^]]*$")


def _validate_include_paths(paths: list[str]) -> None:
    """Raise ValueError if any include_path glob is unsafe or malformed.

    Checks performed (before :func:`fnmatch.translate` can mask problems):
    - non-empty
    - no null bytes
    - no absolute paths
    - no path traversal (``..``)
    - balanced ``[...]`` character classes
    - compiles as valid regex after fnmatch.translate
    """
    for p in paths:
        if not p:
            raise ValueError(f"invalid scope include_path {p!r}: empty pattern")
        if "\x00" in p:
            raise ValueError(f"invalid scope include_path {p!r}: null byte")
        if _ABSOLUTE_PATH_RE.match(p):
            raise ValueError(f"invalid scope include_path {p!r}: absolute path")
        if _TRAVERSAL_RE.search(p):
            raise ValueError(f"invalid scope include_path {p!r}: path traversal")
        if _UNBALANCED_BRACKET_RE.search(p):
            raise ValueError(
                f"invalid scope include_path {p!r}: unbalanced bracket"
            )
        try:
            re.compile(_fnmatch.translate(p))
        except re.error as exc:
            raise ValueError(f"invalid scope include_path {p!r}: {exc}") from exc


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

    # Language check — must match at least one of the listed languages
    all_extensions: list[str] = []
    for lang in invariant.scope.languages:
        all_extensions.extend(_LANGUAGE_EXTENSIONS.get(lang, []))
    if not all_extensions:
        return False
    if not any(file_path.endswith(ext) for ext in all_extensions):
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
    aggregate_bytes = 0

    # Truncate total file count
    if len(changed_files) > MAX_CHANGED_FILES:
        truncated = True
        changed_files = changed_files[:MAX_CHANGED_FILES]

    for cf in changed_files:
        norm = normalize_path(cf.path)

        # Check scope against any invariant — out-of-scope files are silently
        # excluded from coverage (they are not gaps).
        in_any_scope = any(is_in_scope(norm, inv) for inv in invariants)
        if not in_any_scope:
            continue

        if not cf.patch_complete:
            skipped.append(CoverageGap(file=norm, reason="truncated patch"))
            truncated = True
            continue

        # Missing patch on a non-removed in-scope file is a coverage gap.
        # GitHub may omit the patch for large or binary files even when the
        # file is in scope.
        if cf.patch is None and cf.status != "removed":
            skipped.append(
                CoverageGap(
                    file=norm,
                    reason="patch unavailable (file may be too large or binary)",
                )
            )
            truncated = True
            continue

        patch_bytes = len(cf.patch.encode("utf-8")) if cf.patch else 0

        # Per-file check — individual patch must not exceed the ceiling
        if patch_bytes > MAX_PATCH_BYTES:
            skipped.append(
                CoverageGap(
                    file=norm,
                    reason=f"patch exceeds {MAX_PATCH_BYTES}-byte limit ({patch_bytes} bytes)",
                )
            )
            truncated = True
            continue

        # Aggregate check — total in-scope bytes must not exceed the ceiling
        if aggregate_bytes + patch_bytes > MAX_PATCH_BYTES:
            skipped.append(
                CoverageGap(
                    file=norm,
                    reason=f"aggregate patch limit ({MAX_PATCH_BYTES} bytes) would be exceeded",
                )
            )
            truncated = True
            continue

        aggregate_bytes += patch_bytes

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
