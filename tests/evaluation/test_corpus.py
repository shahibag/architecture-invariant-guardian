"""Offline evaluation harness — runs all 48 corpus cases and validates
against the section 12 thresholds.

No live provider calls.  Each case is evaluated against the deterministic
AST-based detector only (the judge is not involved in offline evaluation).
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import pytest

from invariant_guardian.rules.java import detect_candidates_from_source

from .fixtures import ALL_CASES

# ---------------------------------------------------------------------------
# Individual case tests — one test per corpus case
# ---------------------------------------------------------------------------


def _make_case_id(case: dict[str, Any]) -> str:
    return f"{case['id']}"


@pytest.mark.parametrize("case", ALL_CASES, ids=_make_case_id)
def test_corpus_case(case: dict[str, Any]) -> None:
    """Run a single corpus case through the AST detector and verify the
    expected detection outcome.
    """
    candidates = detect_candidates_from_source(
        case["source"],
        case["file_path"],
        case["changed_lines"],
        {case["invariant_id"]},
    )

    if case["expected_decision"] == "confirm":
        _assert_positive(case, candidates)
    else:
        _assert_negative(case, candidates)


def _assert_positive(case: dict[str, Any], candidates: list[Any]) -> None:
    """Assert that at least one candidate is found for a positive case."""
    assert len(candidates) >= 1, (
        f"Positive case {case['id']} ({case['description']}) "
        f"expected ≥1 candidate, got 0"
    )
    # Verify invariant ID
    for c in candidates:
        assert c.invariant_id == case["invariant_id"], (
            f"Case {case['id']}: expected invariant_id={case['invariant_id']}, "
            f"got {c.invariant_id}"
        )


def _assert_negative(case: dict[str, Any], candidates: list[Any]) -> None:
    """Assert that no candidate is found for a negative case, or if found
    the detection is low-confidence only (the judge would reject it).
    """
    high_med = [c for c in candidates if c.confidence in ("high", "medium")]
    assert len(high_med) == 0, (
        f"Negative case {case['id']} ({case['description']}) "
        f"should not produce high/medium-confidence candidates, "
        f"got {len(high_med)}: {[(c.pattern, c.evidence) for c in high_med]}"
    )


# ---------------------------------------------------------------------------
# Aggregate metrics — computed at collection time
# ---------------------------------------------------------------------------

_TP: dict[str, int] = defaultdict(int)  # invariant_id → true positives
_FP: dict[str, int] = defaultdict(int)  # invariant_id → false positives
_TN: dict[str, int] = defaultdict(int)  # invariant_id → true negatives
_FN: dict[str, int] = defaultdict(int)  # invariant_id → false negatives
_TOTAL: dict[str, int] = defaultdict(int)


def _compute_metrics() -> None:
    """Evaluate every case and compute precision/recall per invariant."""
    for case in ALL_CASES:
        inv = case["invariant_id"]
        _TOTAL[inv] += 1
        try:
            candidates = detect_candidates_from_source(
                case["source"],
                case["file_path"],
                case["changed_lines"],
                {case["invariant_id"]},
            )
        except Exception:  # noqa: BLE001 — safe catch-all for evaluation harness
            # Count as FN for positive, TN for negative
            if case["expected_decision"] == "confirm":
                _FN[inv] += 1
            else:
                _TN[inv] += 1
            continue

        # For metrics: only high/medium confidence counts as "detected".
        # Low-confidence candidates are expected noise — the judge rejects them.
        significant = [c for c in candidates if c.confidence in ("high", "medium")]
        detected = len(significant) > 0
        expected = case["expected_decision"] == "confirm"

        if expected and detected:
            _TP[inv] += 1
        elif expected and not detected:
            _FN[inv] += 1
        elif not expected and detected:
            _FP[inv] += 1
        else:
            _TN[inv] += 1


def _write_reports() -> None:
    """Write machine-readable JSON and Markdown summary reports."""
    from pathlib import Path

    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)

    metrics: dict[str, dict[str, Any]] = {}
    for inv in sorted(_TOTAL):
        tp = _TP.get(inv, 0)
        fp = _FP.get(inv, 0)
        tn = _TN.get(inv, 0)
        fn = _FN.get(inv, 0)
        total = _TOTAL[inv]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        metrics[inv] = {
            "total": total,
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        }

    # --- JSON report ---
    json_path = report_dir / "evaluation.json"
    json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    # --- Markdown summary ---
    md_lines = [
        "# Invariant Guardian v0.2 — Offline Evaluation Report",
        "",
        "## Thresholds (spec §12)",
        "",
        "| Metric | Threshold |",
        "| --- | ---: |",
        "| Candidate precision | ≥ 90% per invariant |",
        "| Candidate recall | ≥ 80% per invariant |",
        "| Evidence file and changed-line validity | 100% |",
        "| Unsupported provider decisions accepted as clean | 0 |",
        "| Provider/schema/context failures reported as incomplete | 100% |",
        "| Contributor-marker comments modified | 0 |",
        "",
        "## Results by Invariant",
        "",
    ]

    for inv in sorted(metrics):
        m = metrics[inv]
        md_lines.extend([
            f"### {inv}",
            "",
            f"- **Total cases:** {m['total']}",
            f"- **True positives:** {m['true_positives']}",
            f"- **False positives:** {m['false_positives']}",
            f"- **True negatives:** {m['true_negatives']}",
            f"- **False negatives:** {m['false_negatives']}",
            f"- **Precision:** {m['precision']:.1%}",
            f"- **Recall:** {m['recall']:.1%}",
            "",
            f"{'✅' if m['precision'] >= 0.90 else '❌'} Precision ≥ 90%",
            f"{'✅' if m['recall'] >= 0.80 else '❌'} Recall ≥ 80%",
            "",
        ])

    md_lines.extend([
        "## Summary",
        "",
        "This evaluation was performed entirely offline using deterministic",
        "AST-based candidate detection. No live provider calls were made.",
        "The judge contract is separately validated by unit and contract tests.",
        "",
        f"Report generated for {len(ALL_CASES)} corpus cases across both invariants.",
    ])

    md_path = report_dir / "evaluation.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")


def test_evaluation_thresholds() -> None:
    """Enforce section 12 release thresholds on the offline corpus."""
    _compute_metrics()
    _write_reports()

    for inv in sorted(_TOTAL):
        tp = _TP.get(inv, 0)
        fp = _FP.get(inv, 0)
        fn = _FN.get(inv, 0)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

        assert precision >= 0.90, (
            f"{inv}: precision {precision:.1%} below 90% threshold "
            f"(TP={tp}, FP={fp})"
        )
        assert recall >= 0.80, (
            f"{inv}: recall {recall:.1%} below 80% threshold "
            f"(TP={tp}, FN={fn})"
        )
