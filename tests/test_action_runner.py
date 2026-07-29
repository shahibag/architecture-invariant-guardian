import json
from pathlib import Path

import pytest

from invariant_guardian.action_runner import run


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
