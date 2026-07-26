import json
from pathlib import Path
from unittest.mock import patch

import pytest

from invariant_guardian.action_runner import run
from invariant_guardian.domain.models import AssessmentStatus


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
    assert json.loads(capsys.readouterr().out)["reason"] == "fork PR"
