"""GitHub Action runner — event translation, judgement, publication, outputs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from invariant_guardian.adapters.github.client import GitHubClient
from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge
from invariant_guardian.application import ReviewEngine
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    Coverage,
    ReviewRequest,
    SafeWarning,
)
from invariant_guardian.invariants import load_invariants
from invariant_guardian.rendering.comment import fingerprint, render_comment


def _write_action_outputs(assessment: Assessment) -> None:
    """Write the v0.2 Action outputs to GITHUB_OUTPUT (spec §10)."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return  # not running inside an Action — graceful no-op

    confirmed_count = len(assessment.violations)
    candidate_count = len(assessment.candidates)
    coverage_complete = (
        "false"
        if (assessment.coverage.skipped_files or assessment.coverage.context_truncated)
        else "true"
    )

    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"assessment-status={assessment.status.value}\n")
        f.write(f"confirmed-count={confirmed_count}\n")
        f.write(f"candidate-count={candidate_count}\n")
        f.write(f"coverage-complete={coverage_complete}\n")


def run() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    token = os.environ.get("INPUT_GITHUB-TOKEN")
    if not event_path or not token:
        raise RuntimeError("GITHUB_EVENT_PATH and INPUT_GITHUB-TOKEN are required")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not pull_request:
        raise RuntimeError("Invariant Guardian supports pull_request events only")

    # --- fork PR: assessment_incomplete with all declared outputs -----------
    if pull_request["head"]["repo"].get("fork"):
        assessment = Assessment(
            status=AssessmentStatus.INCOMPLETE,
            coverage=Coverage(),
            warnings=[
                SafeWarning(
                    category="fork",
                    message="Fork PRs are not assessed for architecture invariants.",
                ),
            ],
        )
        _write_action_outputs(assessment)
        print(json.dumps(assessment.model_dump(mode="json")))
        return 0

    client = GitHubClient(token, event["repository"]["full_name"], event["number"])
    with TemporaryDirectory(prefix="invariant-guardian-") as temp:
        # --- load invariants ------------------------------------------------
        invariant_dir = Path(temp) / "invariants"
        client.write_invariants(
            invariant_dir,
            pull_request["base"]["sha"],
            os.environ.get("INPUT_INVARIANT-PATH", ".guardian/invariants"),
        )
        invariants, warnings = load_invariants(invariant_dir)

        # --- fetch changed files via SourceReader (GitHub files endpoint) ---
        changed_files = client.changed_files()

        # --- build request & assess via engine ------------------------------
        engine = ReviewEngine()
        request = ReviewRequest(
            base_sha=pull_request["base"]["sha"],
            head_sha=pull_request["head"]["sha"],
            invariants=invariants,
            changed_files=changed_files,
        )

        # --- wire the judge when credentials are available ------------------
        api_key = os.environ.get("INPUT_LLM-API-KEY") or os.environ.get("LLM_API_KEY")
        judge = None
        if api_key:
            judge = OpenAICompatibleJudge(
                api_key=api_key,
                model=(
                    os.environ.get("INPUT_MODEL")
                    or os.environ.get("LLM_MODEL")
                    or "deepseek-v4-flash"
                ),
                base_url=(
                    os.environ.get("INPUT_LLM-BASE-URL")
                    or os.environ.get("LLM_BASE_URL")
                    or "https://api.deepseek.com"
                ),
            )

        assessment = engine.assess(request, judge=judge)

        # --- merge load-time warnings ---------------------------------------
        assessment.warnings.extend(
            SafeWarning(category="load", message=w) for w in warnings
        )

        # --- publish ---------------------------------------------------------
        key = fingerprint(assessment, pull_request["head"]["sha"])
        client.publish(render_comment(assessment, invariants, key), key)
        _write_action_outputs(assessment)
        print(json.dumps(assessment.model_dump(mode="json")))
    return 0
