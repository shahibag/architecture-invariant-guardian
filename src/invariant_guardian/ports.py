from __future__ import annotations

from pathlib import Path
from typing import Protocol

from invariant_guardian.domain.models import Assessment, CandidateFinding, Invariant


class LLMJudge(Protocol):
    """Provider-neutral evidence judge; adapters must validate their own output."""

    def confirm(
        self,
        invariants: list[Invariant],
        candidates: list[CandidateFinding],
        diff: str,
    ) -> Assessment: ...


class ReviewPublisher(Protocol):
    def publish(self, body: str, fingerprint: str) -> None: ...


class BaseRepositoryReader(Protocol):
    def write_invariants(self, destination: Path, ref: str, directory: str) -> None: ...
