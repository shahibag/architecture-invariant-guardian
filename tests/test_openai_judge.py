import json
from types import SimpleNamespace

import pytest

from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge
from invariant_guardian.domain.models import CandidateFinding, Invariant, InvariantScope, Severity


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
            ]
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

    assert assessment.violations[0].file == CANDIDATE.file
    assert assessment.violations[0].suggested_direction == "Return a DTO instead."
    assert client.chat.completions.request["response_format"]["type"] == "json_object"


def test_judge_raises_on_malformed_response() -> None:
    client = FakeClient({"unexpected": True})
    with pytest.raises(Exception):
        OpenAICompatibleJudge("unused", client=client).confirm(
            [INVARIANT], [CANDIDATE], "diff"
        )


def test_judge_rejects_unknown_candidate_index() -> None:
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

    with pytest.raises(ValueError, match="unknown candidate"):
        OpenAICompatibleJudge("unused", client=client).confirm(
            [INVARIANT], [CANDIDATE], "diff"
        )
