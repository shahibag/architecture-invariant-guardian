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
    JudgeCandidate,
    JudgeRequest,
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


# ---------------------------------------------------------------------------
# evaluate contract — bounded, no full diff
# ---------------------------------------------------------------------------
class TestEvaluateContract:
    def test_evaluate_returns_judge_result(self) -> None:
        client = FakeClient(
            {
                "decisions": [
                    {
                        "candidate_index": 0,
                        "decision": "confirm",
                        "why_it_matters": "Entity leaks.",
                        "suggested_direction": "Use DTO.",
                    }
                ]
            }
        )
        jc = JudgeCandidate(
            index=0,
            invariant_id="no-domain-leak",
            invariant_text="Rule: Do not leak entities.\nRationale: stability.",
            file="src/Foo.java",
            start_line=10,
            end_line=10,
            evidence="public OrderEntity get()",
            context_hunk="@@ -10,0 +11,3 @@\n+    public OrderEntity getOrder() {",
        )
        request = JudgeRequest(candidates=[jc])
        result = OpenAICompatibleJudge("unused", client=client).evaluate(request)
        assert result.truncated is False
        assert len(result.decisions) == 1
        assert result.decisions[0].decision == "confirm"

    def test_evaluate_empty_candidates(self) -> None:
        result = OpenAICompatibleJudge("unused").evaluate(JudgeRequest(candidates=[]))
        assert result.decisions == []
        assert result.truncated is False

    def test_evaluate_malformed_response(self) -> None:
        client = FakeClient({"unexpected": True})
        jc = JudgeCandidate(
            index=0,
            invariant_id="no-domain-leak",
            invariant_text="Rule text",
            file="src/Foo.java",
            start_line=10,
            end_line=10,
            evidence="evidence",
            context_hunk="hunk",
        )
        result = OpenAICompatibleJudge("unused", client=client).evaluate(
            JudgeRequest(candidates=[jc])
        )
        assert result.truncated is True
        assert len(result.errors) >= 1

    def test_evaluate_no_full_diff_in_request(self) -> None:
        """Verify the provider request does NOT contain a full diff."""
        client = FakeClient(
            {
                "decisions": [
                    {
                        "candidate_index": 0,
                        "decision": "reject",
                        "why_it_matters": "Fine.",
                        "suggested_direction": "",
                    }
                ]
            }
        )
        jc = JudgeCandidate(
            index=0,
            invariant_id="no-domain-leak",
            invariant_text="Rule text",
            file="src/Foo.java",
            start_line=10,
            end_line=10,
            evidence="evidence",
            context_hunk="@@ -10,0 +11,3 @@",
        )
        OpenAICompatibleJudge("unused", client=client).evaluate(
            JudgeRequest(candidates=[jc])
        )
        # The request sent to the provider must have NO "diff" key
        sent = client.chat.completions.request
        user_content = json.loads(sent["messages"][1]["content"])
        assert "diff" not in user_content
        # Must have candidates instead
        assert "candidates" in user_content


def test_legacy_context_extractor_has_one_total_limit() -> None:
    from invariant_guardian.adapters.openai.judge import _extract_bounded_context

    patch = "+++ b/src/Foo.java\n" + "\n".join(
        part
        for hunk in range(4)
        for part in [
            f"@@ -0,0 +{90 + hunk},50 @@",
            *[f"+near {hunk}-{line}" for line in range(50)],
        ]
    )
    context = _extract_bounded_context(patch, "src/Foo.java", 100)
    assert len(context.splitlines()) <= 82


def test_adapter_rejects_oversized_messages_before_provider_call() -> None:
    direct_client = FakeClient({"decisions": []})
    direct_judge = OpenAICompatibleJudge("unused", client=direct_client)
    request = JudgeRequest(
        candidates=[
            JudgeCandidate(
                index=0,
                invariant_id="no-domain-leak",
                invariant_text="r" * 60_000,
                file=CANDIDATE.file,
                start_line=10,
                end_line=10,
                evidence=CANDIDATE.evidence,
                context_hunk=CANDIDATE.evidence,
            )
        ]
    )
    result = direct_judge.evaluate(request)
    assert result.truncated is True
    assert result.errors
    assert direct_client.chat.completions.request is None

    legacy_client = FakeClient({"decisions": []})
    legacy_judge = OpenAICompatibleJudge("unused", client=legacy_client)
    huge_invariant = INVARIANT.model_copy(update={"rule": "r" * 60_000})
    assessment = legacy_judge.confirm([huge_invariant], [CANDIDATE], "diff")
    assert assessment.status == AssessmentStatus.INCOMPLETE
    assert assessment.coverage.context_truncated is True
    assert legacy_client.chat.completions.request is None
