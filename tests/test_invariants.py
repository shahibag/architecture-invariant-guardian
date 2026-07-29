from pathlib import Path

from invariant_guardian.invariants import load_invariants

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_valid_markdown_invariants() -> None:
    invariants, warnings = load_invariants(FIXTURES / "invariants")

    assert warnings == []
    assert [invariant.id for invariant in invariants] == [
        "no-domain-leak",
        "no-temporary-monitoring",
    ]
    assert invariants[0].scope.languages == ["java"]


def test_load_invariants_reports_non_mapping_front_matter(tmp_path: Path) -> None:
    (tmp_path / "invalid.md").write_text(
        "---\n- not\n- a\n- mapping\n---\n## Rule\nx\n",
        encoding="utf-8",
    )
    invariants, warnings = load_invariants(tmp_path)
    assert invariants == []
    assert any("mapping" in warning for warning in warnings)
