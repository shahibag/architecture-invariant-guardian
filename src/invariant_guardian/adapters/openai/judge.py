from __future__ import annotations

import re
from enum import StrEnum
from typing import Any, Literal, cast

from openai import APIStatusError, APITimeoutError, AuthenticationError, OpenAI
from pydantic import BaseModel, Field, ValidationError

from invariant_guardian.context import CONTEXT_LINES, MAX_MODEL_CONTEXT_CHARS
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    CandidateFinding,
    Coverage,
    Invariant,
    JudgeCandidate,
    JudgeDecision,
    JudgeRequest,
    JudgeResult,
    ProviderUsage,
    SafeWarning,
    Violation,
)
from invariant_guardian.prompt import build_judge_messages, judge_message_chars

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENAI_TIMEOUT = 60.0  # seconds
PROMPT_VERSION = "guardian-judge-v2"


# ---------------------------------------------------------------------------
# Provider failure classification (spec §9)
# ---------------------------------------------------------------------------

class ProviderFailure(StrEnum):
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_RESPONSE = "invalid_response"
    INTERNAL_ERROR = "internal_error"


def classify_failure(status_code: str | None, error_text: str) -> ProviderFailure:
    """Map a provider error to a safe failure category."""
    text = error_text.lower()
    if status_code in ("401", "403"):
        return ProviderFailure.AUTHENTICATION_ERROR
    if status_code == "429":
        return ProviderFailure.RATE_LIMITED
    if "timed out" in text or "timeout" in text:
        return ProviderFailure.TIMEOUT
    if status_code is not None and status_code.startswith("5"):
        return ProviderFailure.PROVIDER_UNAVAILABLE
    if "invalid" in text and ("json" in text or "response" in text or "schema" in text):
        return ProviderFailure.INVALID_RESPONSE
    # Pydantic ValidationError on the provider output is also invalid response
    if "validation error" in text:
        return ProviderFailure.INVALID_RESPONSE
    return ProviderFailure.INTERNAL_ERROR


def safe_failure_message(failure: ProviderFailure) -> str:
    """Return a user-facing message that never contains raw exception text."""
    messages: dict[ProviderFailure, str] = {
        ProviderFailure.AUTHENTICATION_ERROR: (
            "AI judgment was unavailable (provider API authentication failed)."
        ),
        ProviderFailure.RATE_LIMITED: (
            "AI judgment was unavailable (provider rate limited)."
        ),
        ProviderFailure.TIMEOUT: (
            "AI judgment was unavailable (provider timed out)."
        ),
        ProviderFailure.PROVIDER_UNAVAILABLE: (
            "AI judgment was unavailable (provider_unavailable)."
        ),
        ProviderFailure.INVALID_RESPONSE: (
            "AI judgment was unavailable (invalid response from provider)."
        ),
        ProviderFailure.INTERNAL_ERROR: (
            "AI judgment was unavailable (internal error)."
        ),
    }
    return messages.get(
        failure, "AI judgment was unavailable (provider_unavailable)."
    )


_RETRYABLE_FAILURES = frozenset({
    ProviderFailure.TIMEOUT,
    ProviderFailure.RATE_LIMITED,
    ProviderFailure.PROVIDER_UNAVAILABLE,
})


# ---------------------------------------------------------------------------
# Decision models
# ---------------------------------------------------------------------------


class Decision(BaseModel):
    candidate_index: int = Field(ge=0)
    decision: Literal["confirm", "reject"]
    why_it_matters: str = Field(max_length=600)
    suggested_direction: str = Field(max_length=600)


class JudgeOutput(BaseModel):
    decisions: list[Decision]


# ---------------------------------------------------------------------------
# Strict output validation (spec §9)
# ---------------------------------------------------------------------------


def validate_decisions(output: JudgeOutput, candidate_count: int) -> list[str]:
    """Validate the provider output against the strict contract.

    Returns a list of error descriptions.  An empty list means valid.
    """
    errors: list[str] = []

    if len(output.decisions) != candidate_count:
        errors.append(
            f"expected {candidate_count} decisions, got {len(output.decisions)}"
        )
        # Continue validating what we have — report all issues at once.

    seen: set[int] = set()
    for d in output.decisions:
        if d.candidate_index < 0 or d.candidate_index >= candidate_count:
            errors.append(f"unknown candidate index {d.candidate_index}")
        if d.candidate_index in seen:
            errors.append(f"duplicate candidate index {d.candidate_index}")
        seen.add(d.candidate_index)

    # Check for missing indexes
    expected = set(range(candidate_count))
    missing = expected - seen
    if missing:
        errors.append(f"missing candidate indexes: {sorted(missing)}")

    return errors


# ---------------------------------------------------------------------------
# Judge adapter
# ---------------------------------------------------------------------------


class OpenAICompatibleJudge:
    """Chat Completions adapter for OpenAI and compatible providers.

    Includes request timeout, one retry for transient failures, strict
    output validation, and safe error classification (spec §9).

    The primary entry-point is :meth:`evaluate` which accepts a bounded
    :class:`~invariant_guardian.domain.models.JudgeRequest` — no unbounded
    full diff ever reaches the provider.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-v4-flash",
        base_url: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        self._model = model
        self._client = client or OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=OPENAI_TIMEOUT,
            max_retries=0,  # we implement our own retry policy
        )

    # ------------------------------------------------------------------
    # Primary entry-point — bounded evaluate contract
    # ------------------------------------------------------------------

    def evaluate(self, request: JudgeRequest) -> JudgeResult:
        """Judge the candidates in *request* using only bounded context hunks.

        No unbounded full diff is ever sent to the provider.
        """
        if not request.candidates:
            return JudgeResult(decisions=[])

        # Defense in depth: every public adapter entry point, including the
        # legacy confirm wrapper, must enforce the exact model-visible budget
        # even when callers bypass ReviewEngine.
        if judge_message_chars(request) > MAX_MODEL_CONTEXT_CHARS:
            return JudgeResult(
                decisions=[],
                truncated=True,
                errors=["Model context exceeded the safe request limit."],
            )

        messages = self._build_messages(request)

        failure: ProviderFailure | None = None

        for _attempt in (1, 2):
            try:
                output, input_tokens, output_tokens = self._call_provider(messages)
            except AuthenticationError:
                failure = ProviderFailure.AUTHENTICATION_ERROR
                break
            except APITimeoutError as exc:
                failure = classify_failure(None, str(exc))
                if failure not in _RETRYABLE_FAILURES:
                    break
                continue
            except APIStatusError as exc:
                failure = classify_failure(str(exc.status_code), str(exc))
                if failure not in _RETRYABLE_FAILURES:
                    break
                continue
            except ValidationError:
                failure = ProviderFailure.INVALID_RESPONSE
                break
            except Exception as exc:  # noqa: BLE001 — safe catch-all
                failure = classify_failure(None, str(exc))
                if failure not in _RETRYABLE_FAILURES:
                    break
                continue

            # --- success: validate output ---
            validation_errors = validate_decisions(
                output, len(request.candidates)
            )
            if validation_errors:
                failure = ProviderFailure.INVALID_RESPONSE
                break

            # --- build result ---
            decisions = [
                JudgeDecision(
                    candidate_index=d.candidate_index,
                    decision=d.decision,
                    why_it_matters=d.why_it_matters,
                    suggested_direction=d.suggested_direction,
                )
                for d in output.decisions
            ]
            return JudgeResult(
                decisions=decisions,
                provider_usage=ProviderUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=self._model,
                    prompt_version=PROMPT_VERSION,
                ),
            )

        # --- failure path ---
        assert failure is not None
        return JudgeResult(
            decisions=[],
            truncated=True,
            errors=[safe_failure_message(failure)],
        )

    # ------------------------------------------------------------------
    # Legacy confirm — backward-compatible wrapper (CLI assess_diff)
    # ------------------------------------------------------------------

    def confirm(
        self,
        invariants: list[Invariant],
        candidates: list[CandidateFinding],
        diff: str,
    ) -> Assessment:
        """Legacy entry-point preserved for CLI backward compatibility.

        Converts the old (invariants, candidates, diff) arguments into a
        bounded :class:`JudgeRequest`, delegates to :meth:`evaluate`, then
        converts the :class:`JudgeResult` back to an :class:`Assessment`.

        New callers should use the engine + evaluate path instead.
        """
        if not candidates:
            return Assessment(
                status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS,
                coverage=Coverage(),
            )

        # Build bounded JudgeRequest from legacy args
        invariant_map: dict[str, Invariant] = {inv.id: inv for inv in invariants}
        judge_candidates: list[JudgeCandidate] = []
        for i, c in enumerate(candidates):
            inv = invariant_map.get(c.invariant_id)
            invariant_text = (
                f"Rule: {inv.rule}\nRationale: {inv.rationale}"
                if inv
                else f"Rule: {c.invariant_id}"
            )
            # Extract bounded context from the diff for this candidate. If the
            # legacy caller supplied no parseable per-file hunk, fall back to
            # the already-bounded candidate evidence rather than unrelated
            # whole-diff content.
            context_hunk = (
                _extract_bounded_context(diff, c.file, c.start_line) or c.evidence
            )
            judge_candidates.append(
                JudgeCandidate(
                    index=i,
                    invariant_id=c.invariant_id,
                    invariant_text=invariant_text,
                    file=c.file,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    evidence=c.evidence,
                    context_hunk=context_hunk,
                )
            )

        request = JudgeRequest(candidates=judge_candidates)
        result = self.evaluate(request)

        # Convert JudgeResult → Assessment for backward compat
        if result.truncated or result.errors:
            return Assessment(
                status=AssessmentStatus.INCOMPLETE,
                coverage=Coverage(context_truncated=result.truncated),
                warnings=[
                    SafeWarning(
                        category="provider_failure",
                        message=err,
                    )
                    for err in result.errors
                ] or [
                    SafeWarning(
                        category="provider_failure",
                        message="AI judgment was unavailable.",
                    )
                ],
            )

        violations: list[Violation] = []
        for d in result.decisions:
            if d.decision == "confirm":
                c = candidates[d.candidate_index]
                violations.append(
                    Violation(
                        **c.model_dump(),
                        why_it_matters=d.why_it_matters,
                        suggested_direction=d.suggested_direction,
                    )
                )

        return Assessment(
            status=(
                AssessmentStatus.CONFIRMED_VIOLATIONS
                if violations
                else AssessmentStatus.NO_CONFIRMED_VIOLATIONS
            ),
            violations=violations,
            coverage=Coverage(),
            provider_usage=result.provider_usage,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(request: JudgeRequest) -> list[dict[str, str]]:
        """Build provider messages from a bounded JudgeRequest.

        Only the candidate-specific bounded context hunks are included —
        no unbounded full diff.
        """
        return build_judge_messages(request)

    def _call_provider(
        self, messages: list[dict[str, str]]
    ) -> tuple[JudgeOutput, int | None, int | None]:
        """Make one provider call; return (output, input_tokens, output_tokens).

        Raises exceptions that are caught and classified by the caller.
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=cast(Any, messages),
            response_format=cast(Any, {"type": "json_object"}),
            max_tokens=1200,
            temperature=0,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("provider returned an empty judgment")

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None

        output = JudgeOutput.model_validate_json(content)
        return output, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Bounded context extraction (for legacy confirm compat)
# ---------------------------------------------------------------------------

_CONTEXT_LINES = CONTEXT_LINES


def _extract_bounded_context(diff: str, target_file: str, target_line: int) -> str:
    """Extract a bounded diff hunk around *target_line* in *target_file*.

    Returns at most the lines around the target plus ``_CONTEXT_LINES`` of
    surrounding context — never the full diff.
    """
    selected: list[str] = []
    current_file: str | None = None
    new_line: int | None = None
    header: str | None = None
    hunk_lines: list[str] = []
    max_total_lines = 2 * _CONTEXT_LINES + 2

    def _flush_hunk() -> None:
        nonlocal header, hunk_lines
        remaining = max_total_lines - len(selected)
        if header is not None and hunk_lines and remaining > 1:
            selected.append(header)
            selected.extend(hunk_lines[: remaining - 1])
        header = None
        hunk_lines = []

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            _flush_hunk()
            current_file = line.removeprefix("+++ b/")
            new_line = None
            continue
        if current_file != target_file:
            continue
        if line.startswith("@@"):
            _flush_hunk()
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
            header = line
            continue
        if new_line is None:
            continue

        # Include lines within CONTEXT_LINES of target
        if (
            abs(new_line - target_line) <= _CONTEXT_LINES
            and len(hunk_lines) < max_total_lines - 1
        ):
            hunk_lines.append(line)

        if (
            line.startswith("+") and not line.startswith("+++")
        ) or line.startswith(" "):
            new_line += 1

    _flush_hunk()
    # Never fall back to unrelated whole-diff content when the candidate file
    # or line cannot be located.
    return "\n".join(selected)


OpenAIJudge = OpenAICompatibleJudge
