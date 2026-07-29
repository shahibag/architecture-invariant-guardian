from __future__ import annotations

from pathlib import Path
from typing import Protocol

from invariant_guardian.domain.models import ChangedFile, JudgeRequest, JudgeResult


class LLMJudge(Protocol):
    """Provider-neutral evidence judge; adapters must validate their own output.

    The ``evaluate`` contract accepts a bounded :class:`JudgeRequest` — only
    candidate-specific hunks and invariant text reach the provider.  No
    unbounded full diff is ever sent.
    """

    def evaluate(self, request: JudgeRequest) -> JudgeResult: ...


class ReviewPublisher(Protocol):
    def publish(self, body: str, fingerprint: str) -> None: ...


class BaseRepositoryReader(Protocol):
    def write_invariants(self, destination: Path, ref: str, directory: str) -> None: ...


class SourceReader(Protocol):
    """Fetch changed files and source content from the PR source (e.g. GitHub).

    Each returned :class:`ChangedFile` carries a bounded per-file patch;
    no checkout is performed and PR code is never executed.
    """

    def changed_files(self) -> list[ChangedFile]: ...

    def read_file_at_ref(
        self, path: str, ref: str
    ) -> bytes | None:
        """Return raw file content at *path* for *ref* (exact SHA).

        Returns ``None`` when the file is missing, unavailable, or the
        provider cannot serve it.  The caller must apply size/binary/
        encoding validation before use.
        """
        ...

    def list_source_roots(self, ref: str) -> list[str] | None:
        """Return known Java source-root directories at *ref* (exact SHA).

        Used for cross-module import resolution.  Returns a (possibly empty)
        list of repository-relative paths (e.g. ``["src/main/java"]``), or
        ``None`` when the provider cannot enumerate source roots.

        Implementations must bound entries and response bytes.
        """
        ...
