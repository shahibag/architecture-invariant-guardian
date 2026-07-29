"""Test strict judge-output validation, failure classification, and retry behaviour."""

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from invariant_guardian.adapters.openai.judge import (
    OPENAI_TIMEOUT,
    PROMPT_VERSION,
    JudgeOutput,
    OpenAICompatibleJudge,
    ProviderFailure,
    classify_failure,
    safe_failure_message,
    validate_decisions,
)
from invariant_guardian.domain.models import (
    AssessmentStatus,
    CandidateFinding,
    Invariant,
    InvariantScope,
    Severity,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
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

ONE_CANDIDATE = CandidateFinding(
    invariant_id="no-domain-leak",
    file="src/OrderController.java",
    start_line=10,
    end_line=10,
    pattern="public boundary",
    evidence="public OrderEntity get()",
    confidence="medium",
)

TWO_CANDIDATES = [
    ONE_CANDIDATE,
    CandidateFinding(
        invariant_id="no-domain-leak",
        file="src/UserController.java",
        start_line=5,
        end_line=5,
        pattern="public boundary",
        evidence="public UserEntity post()",
        confidence="medium",
    ),
]


# ---------------------------------------------------------------------------
# validate_decisions — strict output contract
# ---------------------------------------------------------------------------
class TestValidateDecisions:
    """For N candidates a valid result must contain exactly N decisions,
    every index 0..N-1 exactly once, only confirm/reject, and no unknown
    index.  Any violation returns assessment_incomplete."""

    def test_valid_single_confirm(self) -> None:
        output = JudgeOutput(
            decisions=[
                {
                    "candidate_index": 0,
                    "decision": "confirm",
                    "why_it_matters": "Entity exposure.",
                    "suggested_direction": "Return a DTO.",
                }
            ]
        )
        errors = validate_decisions(output, 1)
        assert errors == []

    def test_valid_single_reject(self) -> None:
        output = JudgeOutput(
            decisions=[
                {
                    "candidate_index": 0,
                    "decision": "reject",
                    "why_it_matters": "Acceptable DTO.",
                    "suggested_direction": "",
                }
            ]
        )
        errors = validate_decisions(output, 1)
        assert errors == []

    def test_valid_two_candidates(self) -> None:
        output = JudgeOutput(
            decisions=[
                {"candidate_index": 0, "decision": "confirm", "why_it_matters": "A", "suggested_direction": ""},
                {"candidate_index": 1, "decision": "reject", "why_it_matters": "B", "suggested_direction": ""},
            ]
        )
        errors = validate_decisions(output, 2)
        assert errors == []

    def test_wrong_decision_count(self) -> None:
        """Fewer decisions than candidates → INCOMPLETE."""
        output = JudgeOutput(
            decisions=[
                {"candidate_index": 0, "decision": "confirm", "why_it_matters": "A", "suggested_direction": ""},
            ]
        )
        errors = validate_decisions(output, 2)
        assert len(errors) >= 1
        assert any("expected 2 decisions" in e.lower() for e in errors)

    def test_duplicate_index(self) -> None:
        output = JudgeOutput(
            decisions=[
                {"candidate_index": 0, "decision": "confirm", "why_it_matters": "A", "suggested_direction": ""},
                {"candidate_index": 0, "decision": "reject", "why_it_matters": "B", "suggested_direction": ""},
            ]
        )
        errors = validate_decisions(output, 2)
        assert len(errors) >= 1
        assert any("duplicate" in e.lower() for e in errors)

    def test_unknown_index(self) -> None:
        output = JudgeOutput(
            decisions=[
                {"candidate_index": 0, "decision": "confirm", "why_it_matters": "A", "suggested_direction": ""},
                {"candidate_index": 5, "decision": "reject", "why_it_matters": "B", "suggested_direction": ""},
            ]
        )
        errors = validate_decisions(output, 2)
        assert len(errors) >= 1
        assert any("unknown" in e.lower() for e in errors)

    def test_missing_index(self) -> None:
        """Index 0 is missing, 1 and 2 present → incomplete."""
        output = JudgeOutput(
            decisions=[
                {"candidate_index": 1, "decision": "confirm", "why_it_matters": "A", "suggested_direction": ""},
                {"candidate_index": 2, "decision": "reject", "why_it_matters": "B", "suggested_direction": ""},
            ]
        )
        errors = validate_decisions(output, 3)
        assert len(errors) >= 1
        assert any("missing" in e.lower() for e in errors)

    def test_invalid_decision_value(self) -> None:
        """Only confirm/reject allowed — 'maybe' is invalid."""
        decisions = [
            {"candidate_index": 0, "decision": "maybe", "why_it_matters": "A", "suggested_direction": ""},
        ]
        with pytest.raises(ValidationError):
            JudgeOutput(decisions=decisions)


# ---------------------------------------------------------------------------
# Provider failure classification
# ---------------------------------------------------------------------------
class TestClassifyFailure:
    def test_authentication_error(self) -> None:
        assert classify_failure("401", "invalid api key") == ProviderFailure.AUTHENTICATION_ERROR

    def test_rate_limited_429(self) -> None:
        assert classify_failure("429", "too many requests") == ProviderFailure.RATE_LIMITED

    def test_timeout(self) -> None:
        assert classify_failure(None, "timed out") == ProviderFailure.TIMEOUT

    def test_provider_5xx(self) -> None:
        assert classify_failure("502", "bad gateway") == ProviderFailure.PROVIDER_UNAVAILABLE

    def test_invalid_response_json(self) -> None:
        assert classify_failure(None, "invalid json") == ProviderFailure.INVALID_RESPONSE

    def test_internal_error_default(self) -> None:
        assert classify_failure(None, "something unexpected") == ProviderFailure.INTERNAL_ERROR


# ---------------------------------------------------------------------------
# Safe failure messages (no raw exception text)
# ---------------------------------------------------------------------------
class TestSafeFailureMessages:
    def test_returns_safe_message_for_each_category(self) -> None:
        for failure in ProviderFailure:
            msg = safe_failure_message(failure)
            assert isinstance(msg, str)
            assert len(msg) > 0
            # Must NOT contain "traceback", "exception", raw error jargon
            assert "traceback" not in msg.lower()
            assert "exception" not in msg.lower()

    def test_authentication_message_does_not_leak_key(self) -> None:
        msg = safe_failure_message(ProviderFailure.AUTHENTICATION_ERROR)
        assert "key" not in msg.lower()
        assert "api" in msg.lower()

    def test_provider_unavailable_is_generic(self) -> None:
        msg = safe_failure_message(ProviderFailure.PROVIDER_UNAVAILABLE)
        assert "provider_unavailable" in msg.lower() or "unavailable" in msg.lower()


# ---------------------------------------------------------------------------
# Judge preserves existing behaviour on valid output
# ---------------------------------------------------------------------------
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
            usage=None,
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
        [INVARIANT], [ONE_CANDIDATE], "diff"
    )
    assert assessment.status == AssessmentStatus.CONFIRMED_VIOLATIONS
    assert assessment.violations[0].file == ONE_CANDIDATE.file
    assert assessment.violations[0].suggested_direction == "Return a DTO instead."
    assert client.chat.completions.request["response_format"]["type"] == "json_object"


def test_malformed_response_returns_incomplete() -> None:
    """Malformed provider output returns INCOMPLETE, never raises."""
    client = FakeClient({"unexpected": True})
    assessment = OpenAICompatibleJudge("unused", client=client).confirm(
        [INVARIANT], [ONE_CANDIDATE], "diff"
    )
    assert assessment.status == AssessmentStatus.INCOMPLETE


def test_unknown_candidate_index_returns_incomplete() -> None:
    """Unknown candidate index in provider output → INCOMPLETE, never raises."""
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
        [INVARIANT], [ONE_CANDIDATE], "diff"
    )
    assert assessment.status == AssessmentStatus.INCOMPLETE


# ---------------------------------------------------------------------------
# Timeout and retry behaviour
# ---------------------------------------------------------------------------
class TestOpenAITimeout:
    def test_timeout_constant_is_positive(self) -> None:
        assert OPENAI_TIMEOUT > 0


class TestPromptVersion:
    def test_prompt_version_is_v2(self) -> None:
        assert PROMPT_VERSION == "guardian-judge-v2"
