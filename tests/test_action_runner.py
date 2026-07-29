import json
from pathlib import Path
from typing import cast

import pytest

from invariant_guardian.action_runner import run
from invariant_guardian.domain.models import (
    Assessment,
    AssessmentStatus,
    Coverage,
    ReviewRequest,
)


def test_action_runner_rejects_non_pull_request_events(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    event = tmp_path / "event.json"
    event.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("INPUT_GITHUB-TOKEN", "test-token")

    with pytest.raises(RuntimeError, match="pull_request"):
        run()


def test_action_runner_skips_forked_pull_requests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"head": {"repo": {"fork": True}}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("INPUT_GITHUB-TOKEN", "test-token")

    assert run() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "assessment_incomplete"
    assert len(output["warnings"]) >= 1
    assert any("fork" in w["category"].lower() or "fork" in w["message"].lower()
               for w in output["warnings"])

    # P2.3: Fork assessments must report coverage-complete=false.
    # No changed files were fetched or evaluated.
    assert output["coverage"] == {
        "evaluated_files": [],
        "skipped_files": [],
        "context_truncated": True,
    }, f"Fork coverage must have context_truncated=True, got {output['coverage']}"


def test_action_runner_injects_exact_sha_source_reader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "repository": {"full_name": "owner/repo"},
                "number": 7,
                "pull_request": {
                    "base": {"sha": "base-sha"},
                    "head": {"sha": "head-sha", "repo": {"fork": False}},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("INPUT_GITHUB-TOKEN", "test-token")

    class FakeClient:
        def __init__(self, *args) -> None:
            pass

        def write_invariants(self, *args) -> None:
            pass

        def changed_files(self):
            return []

        def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
            return None

        def publish(self, body: str, fingerprint: str) -> None:
            pass

    client = FakeClient()
    captured: dict[str, object] = {}

    class FakeEngine:
        def assess(self, request, judge=None, source_reader=None):
            captured["request"] = request
            captured["source_reader"] = source_reader
            return Assessment(
                status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS,
                coverage=Coverage(),
            )

    monkeypatch.setattr(
        "invariant_guardian.action_runner.GitHubClient", lambda *args: client
    )
    monkeypatch.setattr("invariant_guardian.action_runner.ReviewEngine", FakeEngine)
    monkeypatch.setattr(
        "invariant_guardian.action_runner.load_invariants", lambda path: ([], [])
    )

    assert run() == 0
    assert captured["source_reader"] is client
    assert cast(ReviewRequest, captured["request"]).head_sha == "head-sha"
