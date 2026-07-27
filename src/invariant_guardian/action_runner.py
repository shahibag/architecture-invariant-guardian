from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from invariant_guardian.adapters.github.client import GitHubClient
from invariant_guardian.adapters.openai.judge import OpenAICompatibleJudge
from invariant_guardian.application import assess_diff
from invariant_guardian.domain.models import Assessment, AssessmentStatus, SafeWarning
from invariant_guardian.invariants import load_invariants
from invariant_guardian.rendering.comment import fingerprint, render_comment


def run() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    token = os.environ.get("INPUT_GITHUB-TOKEN")
    if not event_path or not token:
        raise RuntimeError("GITHUB_EVENT_PATH and INPUT_GITHUB-TOKEN are required")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not pull_request:
        raise RuntimeError("Invariant Guardian supports pull_request events only")
    if pull_request["head"]["repo"].get("fork"):
        print(json.dumps({"status": "assessment_incomplete", "reason": "fork PR"}))
        return 0

    client = GitHubClient(token, event["repository"]["full_name"], event["number"])
    with TemporaryDirectory(prefix="invariant-guardian-") as temp:
        invariant_dir = Path(temp) / "invariants"
        client.write_invariants(
            invariant_dir,
            pull_request["base"]["sha"],
            os.environ.get("INPUT_INVARIANT-PATH", ".guardian/invariants"),
        )
        invariants, warnings = load_invariants(invariant_dir)
        diff = client.pull_diff()
        assessment = assess_diff(invariant_dir, diff)
        assessment.warnings.extend(
            SafeWarning(category="load", message=w) for w in warnings
        )
        api_key = os.environ.get("INPUT_LLM-API-KEY") or os.environ.get("LLM_API_KEY")
        if assessment.candidates and api_key:
            try:
                assessment = OpenAICompatibleJudge(
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
                ).confirm(invariants, assessment.candidates, diff)
            except Exception as exc:
                assessment = Assessment(
                    status=AssessmentStatus.INCOMPLETE,
                    warnings=[
                        *assessment.warnings,
                        SafeWarning(
                            category="provider_failure",
                            message=f"AI evidence judgment failed: {exc}",
                        ),
                    ],
                )
        elif assessment.candidates:
            assessment = Assessment(
                status=AssessmentStatus.INCOMPLETE,
                warnings=[
                    *assessment.warnings,
                    SafeWarning(
                        category="provider_unavailable",
                        message="AI evidence judgment skipped because no compatible-provider API key was available.",
                    ),
                ],
            )
        key = fingerprint(assessment, pull_request["head"]["sha"])
        client.publish(render_comment(assessment, invariants, key), key)
        print(json.dumps(assessment.model_dump(mode="json")))
    return 0
