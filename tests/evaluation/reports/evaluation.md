# Invariant Guardian v0.2 — Offline Evaluation Report

## Thresholds (spec §12)

| Metric | Threshold |
| --- | ---: |
| Candidate precision | ≥ 90% per invariant |
| Candidate recall | ≥ 80% per invariant |
| Evidence file and changed-line validity | 100% |
| Unsupported provider decisions accepted as clean | 0 |
| Provider/schema/context failures reported as incomplete | 100% |
| Contributor-marker comments modified | 0 |

## Results by Invariant

### no-domain-leak

- **Total cases:** 24
- **True positives:** 12
- **False positives:** 0
- **True negatives:** 12
- **False negatives:** 0
- **Precision:** 100.0%
- **Recall:** 100.0%

✅ Precision ≥ 90%
✅ Recall ≥ 80%

### no-temporary-monitoring

- **Total cases:** 24
- **True positives:** 12
- **False positives:** 0
- **True negatives:** 12
- **False negatives:** 0
- **Precision:** 100.0%
- **Recall:** 100.0%

✅ Precision ≥ 90%
✅ Recall ≥ 80%

## Summary

This evaluation was performed entirely offline using deterministic
AST-based candidate detection. No live provider calls were made.
The judge contract is separately validated by unit and contract tests.

Report generated for 48 corpus cases across both invariants.