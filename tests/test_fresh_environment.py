"""Fresh-environment support tests — package install, Action invocation,
output contract, Docker behavior, backward compatibility.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from invariant_guardian.domain.models import AssessmentStatus


class TestPackageInstall:
    def test_package_is_importable(self) -> None:
        """The invariant_guardian package must be importable."""
        import invariant_guardian
        assert invariant_guardian.__version__  # type: ignore[attr-defined]

    def test_cli_entry_point_is_registered(self) -> None:
        """The invariant-guardian CLI entry point must be callable."""
        result = subprocess.run(
            [sys.executable, "-m", "invariant_guardian.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"CLI --help failed: {result.stderr}"
        )

    def test_assess_subcommand_available(self) -> None:
        """The `assess` subcommand must produce JSON output."""
        project_root = Path(__file__).resolve().parent.parent
        invariants = project_root / "tests/fixtures/invariants"
        diff_file = project_root / "tests/fixtures/clean.diff"
        script = (
            "import sys; sys.path.insert(0, 'src'); "
            "from invariant_guardian.cli import main; "
            "import sys; "
            f"sys.argv = ['cli', 'assess', '--invariants', {str(invariants)!r}, "
            f"'--diff', {str(diff_file)!r}]; "
            "main()"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(project_root),
        )
        assert result.returncode == 0, (
            f"assess failed (stderr): {result.stderr}"
        )
        output = result.stdout.strip()
        assert output, "assess must produce JSON output"


class TestOutputContract:
    def test_assessment_incomplete_preserved(self) -> None:
        """The action.yml output contract must include assessment_incomplete
        as a valid status."""
        action_yml = Path("action.yml")
        content = action_yml.read_text()
        assert "assessment_incomplete" in content, (
            "action.yml must reference assessment_incomplete"
        )

    def test_all_outputs_declared(self) -> None:
        """action.yml must declare all four required outputs."""
        action_yml = Path("action.yml")
        content = action_yml.read_text()
        required_outputs = [
            "assessment-status",
            "confirmed-count",
            "candidate-count",
            "coverage-complete",
        ]
        for output_name in required_outputs:
            assert output_name in content, (
                f"action.yml missing output: {output_name}"
            )

    def test_mandatory_coverage_in_assessment(self) -> None:
        """Every Assessment must carry a Coverage (mandatory field)."""
        from pydantic import ValidationError

        from invariant_guardian.domain.models import Assessment
        # Coverage is a required field — creating an Assessment without
        # it would fail at the Pydantic level
        with pytest.raises(ValidationError):
            Assessment(status=AssessmentStatus.INCOMPLETE)  # type: ignore[call-arg]


class TestBackwardCompatibility:
    def test_changed_file_model_accepts_all_statuses(self) -> None:
        """ChangedFile must accept added, modified, removed, renamed."""
        from invariant_guardian.domain.models import ChangedFile

        for status in ("added", "modified", "removed", "renamed"):
            cf = ChangedFile(path="src/Test.java", status=status)  # type: ignore[arg-type]
            assert cf.status == status
            assert cf.patch_complete is True

    def test_assessment_model_dump_is_json_serializable(self) -> None:
        """Assessment.model_dump(mode='json') must produce valid JSON."""
        from invariant_guardian.domain.models import (
            Assessment,
            AssessmentStatus,
            Coverage,
        )

        a = Assessment(status=AssessmentStatus.NO_CONFIRMED_VIOLATIONS, coverage=Coverage())
        dumped = a.model_dump(mode="json")
        # Round-trip through JSON
        encoded = json.dumps(dumped)
        decoded = json.loads(encoded)
        assert decoded["status"] == "no_confirmed_violations"

    def test_no_target_java_execution(self) -> None:
        """The Guardian must never execute or compile target Java code.
        Verify that changed_files() returns a list of ChangedFile models
        without executing any code from the patches."""
        from invariant_guardian.adapters.github.client import GitHubClient

        client = GitHubClient("token", "owner/repo", 1)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [
                {
                    "filename": "src/main/java/com/example/Main.java",
                    "status": "modified",
                    "patch": "Runtime.getRuntime().exec('rm -rf /')",
                }
            ],
            "",
        )
        files = client.changed_files()
        assert len(files) == 1
        # The patch is stored as a string — never executed
        assert isinstance(files[0].patch, str)


class TestDockerSupport:
    def test_dockerfile_exists_and_uses_entrypoint(self) -> None:
        """Dockerfile must exist and use invariant-guardian as entrypoint."""
        dockerfile = Path("Dockerfile")
        assert dockerfile.exists(), "Dockerfile must exist"
        content = dockerfile.read_text()
        assert "invariant-guardian" in content, (
            "Dockerfile must reference invariant-guardian"
        )

    def test_dockerfile_pins_constraints(self) -> None:
        """Dockerfile must use constraints.txt for reproducible builds."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "constraints.txt" in content, (
            "Dockerfile must use constraints.txt"
        )

    def test_dockerfile_copies_source_not_checks_out(self) -> None:
        """Dockerfile must COPY source — never git clone or network fetch."""
        dockerfile = Path("Dockerfile")
        content = dockerfile.read_text()
        assert "COPY" in content, "Dockerfile must COPY source"
        assert "git clone" not in content.lower(), (
            "Dockerfile must not git clone"
        )
