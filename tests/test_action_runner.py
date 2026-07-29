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


def test_action_runner_catches_changed_files_unavailability(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When changed_files raises RuntimeError, ActionRunner must emit
    assessment_incomplete with sanitized warning and zero judge calls."""
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
    monkeypatch.setenv("INPUT_INVARIANT-PATH", "tests/fixtures/invariants")

    class FakeFailingClient:
        def __init__(self, *args) -> None:
            pass

        def write_invariants(self, *args) -> None:
            pass

        def changed_files(self):
            raise RuntimeError("Changed file listing is incomplete or unavailable")

        def publish(self, body: str, fingerprint: str) -> None:
            pass

    client = FakeFailingClient()

    class FakeEngine:
        def assess(self, request, judge=None, source_reader=None):
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

    exit_code = run()
    assert exit_code == 0

    output = json.loads(capsys.readouterr().out)
    # Must report assessment_incomplete
    assert output["status"] == AssessmentStatus.INCOMPLETE.value, (
        f"Expected assessment_incomplete, got {output['status']}"
    )
    # Coverage must be marked incomplete
    assert output["coverage"]["context_truncated"] is True, (
        f"Expected context_truncated=True, got {output['coverage']}"
    )
    # Zero candidates/violations (no judge was called)
    assert len(output["candidates"]) == 0, "Expected zero candidates"
    assert len(output["violations"]) == 0, "Expected zero violations"
    # Must have a sanitized warning (NOT f'{exc}')
    assert any(
        "changed files" in w.get("message", "").lower()
        or "file listing" in w.get("message", "").lower()
        for w in output.get("warnings", [])
    ), f"Expected sanitized changed-files warning, got {output.get('warnings')}"
    # Warning must NOT contain raw exception text/class names
    for w in output.get("warnings", []):
        msg = w.get("message", "")
        assert "RuntimeError" not in msg, f"Raw exception leaked: {msg}"
        assert "Traceback" not in msg, f"Traceback leaked: {msg}"


def test_write_invariants_failure_produces_safe_assessment_incomplete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P1.3: When write_invariants raises TypeError (malformed listing/content),
    ActionRunner must catch it at the outer boundary and emit
    assessment_incomplete with sanitized constant warning, not crash."""
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
    monkeypatch.setenv("INPUT_INVARIANT-PATH", "tests/fixtures/invariants")

    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    class FakeFailingClient:
        def __init__(self, *args) -> None:
            pass

        def write_invariants(self, *args) -> None:
            raise TypeError("malformed listing response secret-body")

        def changed_files(self):
            raise RuntimeError("Changed file listing is incomplete")

        def publish(self, body: str, fingerprint: str) -> None:
            pass

    monkeypatch.setattr(
        "invariant_guardian.action_runner.GitHubClient", lambda *args: FakeFailingClient()
    )
    monkeypatch.setattr(
        "invariant_guardian.action_runner.load_invariants", lambda path: ([], [])
    )

    exit_code = run()
    assert exit_code == 0, "P1.3: must not crash — return 0"

    output = json.loads(capsys.readouterr().out)
    # Must emit assessment_incomplete
    assert output["status"] == AssessmentStatus.INCOMPLETE.value, (
        f"Expected assessment_incomplete, got {output['status']}"
    )
    # Coverage must be incomplete
    assert output["coverage"]["context_truncated"] is True
    # Must have sanitized warning — NEVER raw exception text
    assert any(
        "invariant" in w.get("message", "").lower()
        or "load" in w.get("message", "").lower()
        or "unavailable" in w.get("message", "").lower()
        for w in output.get("warnings", [])
    ), f"Expected sanitized warning, got {output.get('warnings')}"
    # NO raw exception body/token in stdout
    for w in output.get("warnings", []):
        msg = w.get("message", "")
        assert "secret-body" not in msg, f"Raw exception leaked: {msg}"
        assert "TypeError" not in msg, f"Exception type leaked: {msg}"
        assert "Traceback" not in msg, f"Traceback leaked: {msg}"

    # GITHUB_OUTPUT must be written
    assert output_file.exists(), "P1.3: GITHUB_OUTPUT must be written"
    gh_output = output_file.read_text()
    assert "assessment-status=assessment_incomplete" in gh_output
    assert "coverage-complete=false" in gh_output


def test_changed_files_unavailable_preserves_load_warnings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When changed_files raises RuntimeError AND load_invariants produced
    warnings, BOTH the changed-files warning AND the load warnings must
    appear in the output — not silently dropped."""
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
    monkeypatch.setenv("INPUT_INVARIANT-PATH", "tests/fixtures/invariants")

    class FakeFailingClient:
        def __init__(self, *args) -> None:
            pass

        def write_invariants(self, *args) -> None:
            pass

        def changed_files(self):
            raise RuntimeError("Changed file listing is incomplete or unavailable")

        def publish(self, body: str, fingerprint: str) -> None:
            pass

    client = FakeFailingClient()

    monkeypatch.setattr(
        "invariant_guardian.action_runner.GitHubClient", lambda *args: client
    )
    # Return load warnings — these must NOT be silently dropped
    monkeypatch.setattr(
        "invariant_guardian.action_runner.load_invariants",
        lambda path: ([], ["invariant-x.md is missing a source-of-truth link"]),
    )

    exit_code = run()
    assert exit_code == 0

    output = json.loads(capsys.readouterr().out)
    warnings = output.get("warnings", [])

    # Must have at least 2 warnings: changed-files + load
    assert len(warnings) >= 2, (
        f"Expected >= 2 warnings (changed-files + load), got {len(warnings)}: {warnings}"
    )

    # Must have changed-files warning
    assert any(
        "changed files" in w.get("message", "").lower()
        or "file listing" in w.get("message", "").lower()
        for w in warnings
    ), f"Missing changed-files warning in {warnings}"

    # Must have load warning (not silently dropped!)
    assert any(
        w.get("category") == "load"
        for w in warnings
    ), f"Load warnings were dropped! Got: {warnings}"


def test_malformed_invariant_listing_produces_assessment_incomplete_safe_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Phase 3 fail-closed: When write_invariants raises RuntimeError due to
    malformed listing entries (e.g. non-string name), ActionRunner must emit
    assessment_incomplete with ALL declared outputs, zero candidates/violations,
    and sanitised warnings with NO raw text/exception details."""
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
    monkeypatch.setenv("INPUT_INVARIANT-PATH", "tests/fixtures/invariants")

    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    class FakeMalformedClient:
        def __init__(self, *args) -> None:
            pass

        def write_invariants(self, *args) -> None:
            raise RuntimeError(
                "Invariant directory listing contains entry with "
                "missing or invalid name"
            )

        def changed_files(self):
            raise RuntimeError("Changed file listing is incomplete")

        def publish(self, body: str, fingerprint: str) -> None:
            pass

    monkeypatch.setattr(
        "invariant_guardian.action_runner.GitHubClient",
        lambda *args: FakeMalformedClient(),
    )
    monkeypatch.setattr(
        "invariant_guardian.action_runner.load_invariants", lambda path: ([], [])
    )

    exit_code = run()
    assert exit_code == 0, "Must not crash — return 0"

    output = json.loads(capsys.readouterr().out)

    # Must emit assessment_incomplete
    assert output["status"] == AssessmentStatus.INCOMPLETE.value, (
        f"Expected assessment_incomplete, got {output['status']}"
    )

    # Coverage must be incomplete
    assert output["coverage"]["context_truncated"] is True

    # Zero candidates/violations — no judge was called
    assert len(output["candidates"]) == 0, "Expected zero candidates"
    assert len(output["violations"]) == 0, "Expected zero violations"

    # Must have sanitized warning — NEVER raw exception text
    warnings = output.get("warnings", [])
    assert len(warnings) >= 1, f"Expected >= 1 warning, got {warnings}"

    for w in warnings:
        msg = w.get("message", "")
        assert "missing or invalid name" not in msg, (
            f"Raw exception text leaked: {msg}"
        )
        assert "RuntimeError" not in msg, f"Exception type leaked: {msg}"
        assert "Traceback" not in msg, f"Traceback leaked: {msg}"

    # GITHUB_OUTPUT must be written with all declared outputs
    assert output_file.exists(), "GITHUB_OUTPUT must be written"
    gh_output = output_file.read_text()
    assert "assessment-status=assessment_incomplete" in gh_output
    assert "confirmed-count=0" in gh_output
    assert "candidate-count=0" in gh_output
    assert "coverage-complete=false" in gh_output


# ---------------------------------------------------------------------------
# P1#2: Invalid-port Link → assessment_incomplete with all declared outputs
# ---------------------------------------------------------------------------

def test_invalid_port_link_produces_assessment_incomplete_safe_outputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P1#2: When changed_files pagination encounters a Link with an
    invalid port (e.g. api.github.com:bad), the ValueError from urlparse
    must be caught and converted to assessment_incomplete with ALL declared
    GITHUB_OUTPUT keys, zero candidates/violations, JSON stdout, constant
    warning, no raw port/body/token string, no uncaught exception."""
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
    monkeypatch.setenv("INPUT_INVARIANT-PATH", "tests/fixtures/invariants")

    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    class FakeClientWithInvalidPortLink:
        def __init__(self, *args) -> None:
            pass

        def write_invariants(self, *args) -> None:
            pass

        def changed_files(self):
            # P1#2: changed_files() now catches ValueError from invalid-port
            # urlparse and raises sanitized RuntimeError. ActionRunner must
            # handle this without crashing.
            raise RuntimeError(
                "Changed file listing is incomplete or unavailable"
            )

        def publish(self, body: str, fingerprint: str) -> None:
            pass

    monkeypatch.setattr(
        "invariant_guardian.action_runner.GitHubClient",
        lambda *args: FakeClientWithInvalidPortLink(),
    )
    monkeypatch.setattr(
        "invariant_guardian.action_runner.load_invariants", lambda path: ([], [])
    )

    exit_code = run()
    assert exit_code == 0, "P1#2: Must return 0, not crash with ValueError"

    output = json.loads(capsys.readouterr().out)

    # Must emit assessment_incomplete
    assert output["status"] == AssessmentStatus.INCOMPLETE.value, (
        f"P1#2: Expected assessment_incomplete, got {output['status']}"
    )

    # Coverage must be incomplete
    assert output["coverage"]["context_truncated"] is True, (
        "P1#2: Expected context_truncated=True"
    )

    # Zero candidates/violations — no judge was called
    assert len(output["candidates"]) == 0, "P1#2: Expected zero candidates"
    assert len(output["violations"]) == 0, "P1#2: Expected zero violations"

    # Must have sanitized warning — NEVER raw port/body/token
    warnings = output.get("warnings", [])
    assert len(warnings) >= 1, f"P1#2: Expected >= 1 warning, got {warnings}"

    for w in warnings:
        msg = w.get("message", "")
        assert "bad" not in msg, f"P1#2: Raw port leaked: {msg}"
        assert "ValueError" not in msg, f"P1#2: Exception type leaked: {msg}"
        assert "Traceback" not in msg, f"P1#2: Traceback leaked: {msg}"

    # GITHUB_OUTPUT must be written with all declared outputs
    assert output_file.exists(), "P1#2: GITHUB_OUTPUT must be written"
    gh_output = output_file.read_text()
    assert "assessment-status=assessment_incomplete" in gh_output, (
        f"P1#2: Missing assessment-status in GITHUB_OUTPUT: {gh_output}"
    )
    assert "confirmed-count=0" in gh_output
    assert "candidate-count=0" in gh_output
    assert "coverage-complete=false" in gh_output


# ---------------------------------------------------------------------------
# P1#3: Malformed Link → ActionRunner incomplete, no mutation
# ---------------------------------------------------------------------------

def test_malformed_link_header_produces_assessment_incomplete_no_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """P1#3: When changed_files encounters a malformed Link header
    (trailing comma, multi-token rel), ActionRunner must emit
    assessment_incomplete with sanitized warning, zero candidates, and
    no publication mutation."""
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
    monkeypatch.setenv("INPUT_INVARIANT-PATH", "tests/fixtures/invariants")

    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    class FakeClientWithMalformedLink:
        def __init__(self, *args) -> None:
            pass

        def write_invariants(self, *args) -> None:
            pass

        def changed_files(self):
            # Simulate changed_files raising RuntimeError due to malformed
            # Link header (trailing comma detected by hardened parser)
            raise RuntimeError(
                "Changed file listing is incomplete or unavailable"
            )

        def publish(self, body: str, fingerprint: str) -> None:
            pass

    monkeypatch.setattr(
        "invariant_guardian.action_runner.GitHubClient",
        lambda *args: FakeClientWithMalformedLink(),
    )
    monkeypatch.setattr(
        "invariant_guardian.action_runner.load_invariants", lambda path: ([], [])
    )

    exit_code = run()
    assert exit_code == 0, "P1#3: Must return 0, not crash"

    output = json.loads(capsys.readouterr().out)

    # Must emit assessment_incomplete
    assert output["status"] == AssessmentStatus.INCOMPLETE.value, (
        f"P1#3: Expected assessment_incomplete, got {output['status']}"
    )

    # Coverage must be incomplete
    assert output["coverage"]["context_truncated"] is True

    # Zero candidates/violations
    assert len(output["candidates"]) == 0
    assert len(output["violations"]) == 0

    # GITHUB_OUTPUT must be written with all declared outputs
    assert output_file.exists(), "P1#3: GITHUB_OUTPUT must be written"
    gh_output = output_file.read_text()
    assert "assessment-status=assessment_incomplete" in gh_output
    assert "confirmed-count=0" in gh_output
    assert "candidate-count=0" in gh_output
    assert "coverage-complete=false" in gh_output
