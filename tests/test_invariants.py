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

