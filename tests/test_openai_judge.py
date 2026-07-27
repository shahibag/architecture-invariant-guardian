"""Contract tests for the OpenAI-compatible judge — valid, invalid, and
malformed responses."""

import json
from types import SimpleNamespace

from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge
from invariant_guardian.domain.models import (
    AssessmentStatus,
    CandidateFinding,
    Invariant,
    InvariantScope,
    Severity,
)

INVARIANT = Invariant(
    id="no-domain-leak",
    title="No domain leak",
    severity=Severity.ERROR,
    scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
    rule="Do not leak entities.",
    rationale="Public contracts should remain stable.",
    violating_examples="Return OrderEntity.",
    acceptable_examples="Return OrderResponse.",
)
CANDIDATE = CandidateFinding(
    invariant_id="no-domain-leak",
    file="src/OrderController.java",
    start_line=10,
    end_line=10,
    pattern="public boundary",
    evidence="public OrderEntity get()",
    confidence="medium",
)


class FakeResponses:
    def __init__(self, output: dict) -> None:
        self._output = output
        self.request: dict | None = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps(self._output))
                )
            ],
            usage=None,  # v0.2 — response.usage must exist
        )


class FakeClient:
    def __init__(self, output: dict) -> None:
        self.chat = SimpleNamespace(completions=FakeResponses(output))


def test_judge_confirms_only_an_existing_candidate() -> None:
    client = FakeClient(
        {
            "decisions": [
                {
                    "candidate_index": 0,
                    "decision": "confirm",
                    "why_it_matters": "Entity shape becomes a public contract.",
                    "suggested_direction": "Return a DTO instead.",
                }
            ]
        }
    )
    assessment = OpenAICompatibleJudge("unused", client=client).confirm(
        [INVARIANT], [CANDIDATE], "diff"
    )

    assert assessment.status == AssessmentStatus.CONFIRMED_VIOLATIONS
    assert assessment.violations[0].file == CANDIDATE.file
    assert assessment.violations[0].suggested_direction == "Return a DTO instead."
    assert client.chat.completions.request["response_format"]["type"] == "json_object"


def test_malformed_response_returns_incomplete() -> None:
    """A response that doesn't match the expected schema returns INCOMPLETE,
    never raises."""
    client = FakeClient({"unexpected": True})
    assessment = OpenAICompatibleJudge("unused", client=client).confirm(
        [INVARIANT], [CANDIDATE], "diff"
    )
    assert assessment.status == AssessmentStatus.INCOMPLETE
    assert assessment.violations == []
    assert any("invalid" in w.message.lower() for w in assessment.warnings)


def test_unknown_candidate_index_returns_incomplete() -> None:
    """An unknown candidate index in the provider output returns INCOMPLETE."""
    client = FakeClient(
        {
            "decisions": [
                {
                    "candidate_index": 4,
                    "decision": "confirm",
                    "why_it_matters": "Unsupported.",
                    "suggested_direction": "Unsupported.",
                }
            ]
        }
    )
    assessment = OpenAICompatibleJudge("unused", client=client).confirm(
        [INVARIANT], [CANDIDATE], "diff"
    )
    assert assessment.status == AssessmentStatus.INCOMPLETE
    assert assessment.violations == []


def test_duplicate_decision_index_returns_incomplete() -> None:
    client = FakeClient(
        {
            "decisions": [
                {"candidate_index": 0, "decision": "confirm", "why_it_matters": "A", "suggested_direction": ""},
                {"candidate_index": 0, "decision": "reject", "why_it_matters": "B", "suggested_direction": ""},
            ]
        }
    )
    assessment = OpenAICompatibleJudge("unused", client=client).confirm(
        [INVARIANT], [CANDIDATE], "diff"
    )
    assert assessment.status == AssessmentStatus.INCOMPLETE


def test_empty_candidates_returns_clean() -> None:
    assessment = OpenAICompatibleJudge("unused").confirm([INVARIANT], [], "diff")
    assert assessment.status == AssessmentStatus.NO_CONFIRMED_VIOLATIONS
    assert assessment.violations == []
