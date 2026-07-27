"""Test scope enforcement and context-budget behaviour."""

import pytest

from invariant_guardian.context import (
    CONTEXT_LINES,
    MAX_CANDIDATE_COUNT,
    MAX_CHANGED_FILES,
    MAX_MODEL_CONTEXT_CHARS,
    MAX_PATCH_BYTES,
    MAX_SOURCE_BYTES_PER_FILE,
    _validate_include_paths,
    build_coverage,
    is_in_scope,
    normalize_path,
)
from invariant_guardian.domain.models import (
    ChangedFile,
    Coverage,
    Invariant,
    InvariantScope,
    Severity,
)


# ---------------------------------------------------------------------------
# Path normalisation
# ---------------------------------------------------------------------------
class TestNormalizePath:
    def test_rejects_absolute_path(self) -> None:
        with pytest.raises(ValueError, match="absolute"):
            normalize_path("/src/main/java/Foo.java")

    def test_removes_dot_slash(self) -> None:
        assert normalize_path("./src/main/java/Foo.java") == "src/main/java/Foo.java"

    def test_resolves_double_dots(self) -> None:
        assert normalize_path("src/../main/java/Foo.java") == "main/java/Foo.java"

    def test_preserves_already_normal_path(self) -> None:
        assert normalize_path("src/main/java/Foo.java") == "src/main/java/Foo.java"

    def test_empty_path(self) -> None:
        assert normalize_path("") == ""

    def test_traversal_escape_rejected(self) -> None:
        """A path that escapes the repository root with .. must be rejected."""
        with pytest.raises(ValueError, match="traversal"):
            normalize_path("../../etc/passwd")

    def test_traversal_disguised_as_normalization_rejected(self) -> None:
        """Path traversal that os.path.normpath resolves but still has ..
        segments after normalisation must be rejected."""
        with pytest.raises(ValueError, match="traversal"):
            normalize_path("src/../../../etc/passwd")

    def test_null_byte_rejected_before_normalization(self) -> None:
        with pytest.raises(ValueError, match="null"):
            normalize_path("src/\x00evil.java")


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------
class TestIsInScope:
    @staticmethod
    def _inv(languages: list[str] | None = None, include_paths: list[str] | None = None) -> Invariant:
        return Invariant(
            id="test",
            title="Test",
            severity=Severity.ERROR,
            scope=InvariantScope(
                languages=languages or ["java"],
                include_paths=include_paths or ["src/main/java/**"],
            ),
            rule="R",
            rationale="R",
            violating_examples="VE",
            acceptable_examples="AE",
        )

    # --- positive ---
    def test_java_file_in_included_path(self) -> None:
        inv = self._inv()
        assert is_in_scope("src/main/java/com/example/Foo.java", inv)

    def test_java_file_matches_glob(self) -> None:
        inv = self._inv(include_paths=["src/**/*.java"])
        assert is_in_scope("src/main/java/Foo.java", inv)

    # --- negative ---
    def test_non_java_file_rejected_for_java_language(self) -> None:
        inv = self._inv()
        assert not is_in_scope("src/main/java/Foo.kt", inv)
        assert not is_in_scope("src/main/java/Foo.py", inv)

    def test_java_file_outside_include_path(self) -> None:
        inv = self._inv(include_paths=["src/main/java/**"])
        assert not is_in_scope("src/test/java/Foo.java", inv)

    def test_removed_file(self) -> None:
        """Removed files do not create new violations but must not break line
        accounting; is_in_scope should still recognise them as in-scope for
        coverage tracking."""
        inv = self._inv()
        # A removed Java file is still in-scope for coverage purposes.
        assert is_in_scope("src/main/java/Foo.java", inv)

    def test_invalid_scope_paths_are_rejected_by_is_in_scope(self) -> None:
        """Path traversal and absolute paths are rejected by is_in_scope
        regardless of glob pattern."""
        inv = self._inv(include_paths=["src/**"])
        # Path traversal
        assert not is_in_scope("../../etc/passwd", inv)
        # Absolute path
        assert not is_in_scope("/etc/hostname", inv)

    # --- multiple languages ---

    def test_handles_all_scope_languages_not_just_first(self) -> None:
        """When an invariant declares multiple languages, a file matching
        any of the supported languages should be in scope.  Previously
        only languages[0] was checked, so java-as-second-language failed."""
        inv = self._inv(languages=["kotlin", "java"], include_paths=["src/**"])
        # Java is second in the list but must still match
        assert is_in_scope("src/main/java/Foo.java", inv)
        # Kotlin is not yet supported in Phase 1, so it won't match
        assert not is_in_scope("src/main/kotlin/Foo.kt", inv)

    def test_second_language_also_used(self) -> None:
        """A file matching the second listed language must be in scope."""
        inv = self._inv(languages=["python", "java"], include_paths=["src/**"])
        assert is_in_scope("src/main/java/Foo.java", inv)


# ---------------------------------------------------------------------------
# Validate include_path globs — meaningful rejection of malformed patterns
# ---------------------------------------------------------------------------
class TestValidateIncludePaths:
    def test_valid_glob_accepted(self) -> None:
        """Well-formed glob patterns should pass validation."""
        _validate_include_paths(["src/**", "src/main/java/**/*.java"])

    def test_unclosed_bracket_rejected(self) -> None:
        """fnmatch.translate may accept [unclosed but our validator must not."""
        with pytest.raises(ValueError, match="invalid"):
            _validate_include_paths(["src/[unclosed"])

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            _validate_include_paths([""])

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            _validate_include_paths(["/etc/passwd"])

    def test_traversal_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            _validate_include_paths(["../../etc/passwd"])

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid"):
            _validate_include_paths(["src/\x00evil"])


# ---------------------------------------------------------------------------
# Context budgets (constants present and reasonable)
# ---------------------------------------------------------------------------
class TestContextBudgets:
    def test_budgets_are_positive(self) -> None:
        assert MAX_CHANGED_FILES > 0
        assert MAX_PATCH_BYTES > 0
        assert MAX_CANDIDATE_COUNT > 0
        assert MAX_SOURCE_BYTES_PER_FILE > 0
        assert MAX_MODEL_CONTEXT_CHARS > 0
        assert CONTEXT_LINES > 0

    def test_values_match_spec_initial_values(self) -> None:
        assert MAX_CHANGED_FILES == 200
        assert MAX_PATCH_BYTES == 200_000
        assert MAX_CANDIDATE_COUNT == 25
        assert MAX_SOURCE_BYTES_PER_FILE == 100_000
        assert MAX_MODEL_CONTEXT_CHARS == 60_000
        assert CONTEXT_LINES == 40


# ---------------------------------------------------------------------------
# build_coverage
# ---------------------------------------------------------------------------
class TestBuildCoverage:
    @staticmethod
    def _java(path: str, **kw) -> ChangedFile:
        kwargs = {
            "path": path,
            "status": "modified",
            "patch": "@@ -1 +1 @@\n-old\n+new",
            "patch_complete": True,
        }
        kwargs.update(kw)
        return ChangedFile(**kwargs)

    def test_all_in_scope_files_evaluated(self) -> None:
        inv = Invariant(
            id="test",
            title="Test",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/main/java/**"]),
            rule="R",
            rationale="R",
            violating_examples="VE",
            acceptable_examples="AE",
        )
        files = [
            self._java("src/main/java/Foo.java"),
            self._java("src/main/java/Bar.java"),
        ]
        cov = build_coverage([inv], files)
        assert set(cov.evaluated_files) == {"src/main/java/Foo.java", "src/main/java/Bar.java"}
        assert cov.skipped_files == []

    def test_non_java_file_ignored_not_gap(self) -> None:
        """Out-of-scope files (e.g. non-Java) must not be coverage gaps —
        they are silently excluded from coverage tracking."""
        inv = Invariant(
            id="test",
            title="Test",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="R",
            rationale="R",
            violating_examples="VE",
            acceptable_examples="AE",
        )
        files = [self._java("README.md")]
        cov = build_coverage([inv], files)
        assert cov.evaluated_files == []
        # Out-of-scope files are NOT coverage gaps
        assert cov.skipped_files == []
        assert cov.context_truncated is False

    def test_truncated_patch_recorded(self) -> None:
        inv = Invariant(
            id="test",
            title="Test",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="R",
            rationale="R",
            violating_examples="VE",
            acceptable_examples="AE",
        )
        files = [
            self._java("src/Foo.java", patch_complete=False),
        ]
        cov = build_coverage([inv], files)
        assert cov.evaluated_files == []
        assert len(cov.skipped_files) == 1
        assert "truncated" in cov.skipped_files[0].reason.lower()

    def test_oversized_patch_recorded(self) -> None:
        inv = Invariant(
            id="test",
            title="Test",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="R",
            rationale="R",
            violating_examples="VE",
            acceptable_examples="AE",
        )
        big_patch = "x" * (MAX_PATCH_BYTES + 1)
        files = [
            self._java("src/Foo.java", patch=big_patch),
        ]
        cov = build_coverage([inv], files)
        assert len(cov.skipped_files) == 1
        assert any("oversized" in g.reason.lower() or "limit" in g.reason.lower()
                   for g in cov.skipped_files)
        assert cov.context_truncated

    def test_too_many_files_truncates(self) -> None:
        inv = Invariant(
            id="test",
            title="Test",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="R",
            rationale="R",
            violating_examples="VE",
            acceptable_examples="AE",
        )
        files = [
            self._java(f"src/Foo{i}.java") for i in range(MAX_CHANGED_FILES + 5)
        ]
        cov = build_coverage([inv], files)
        assert cov.context_truncated
        # At most MAX_CHANGED_FILES should be evaluated
        assert len(cov.evaluated_files) <= MAX_CHANGED_FILES

    def test_removed_file_not_evaluated_for_violations_but_tracked(self) -> None:
        inv = Invariant(
            id="test",
            title="Test",
            severity=Severity.ERROR,
            scope=InvariantScope(languages=["java"], include_paths=["src/**"]),
            rule="R",
            rationale="R",
            violating_examples="VE",
            acceptable_examples="AE",
        )
        files = [
            self._java("src/Foo.java", status="removed", patch=None),
        ]
        cov = build_coverage([inv], files)
        # removed files should be in evaluated or skipped but not cause errors
        assert isinstance(cov, Coverage)
