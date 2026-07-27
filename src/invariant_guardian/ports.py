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
    """Fetch changed files from the PR source (e.g. GitHub files endpoint).

    Each returned :class:`ChangedFile` carries a bounded per-file patch;
    no checkout is performed and PR code is never executed.
    """

    def changed_files(self) -> list[ChangedFile]: ...
