# Invariant Guardian v0.2 — Offline Evaluation Report

Manifest: `tests/evaluation/manifest.yaml` (loaded: True)
Java version: 21
Corpus size: 53 cases

## Thresholds (spec §12)

| Metric | Threshold |
| --- | ---: |
| Candidate precision | ≥ 90% per invariant |
| Candidate recall | ≥ 80% per invariant |
| Evidence file and changed-line validity | 100% |
| Unsupported provider decisions accepted as clean | 0 |

## Candidate Detection Results

### no-domain-leak

- **Total cases:** 28
- **True positives:** 14
- **False positives:** 0
- **True negatives:** 14
- **False negatives:** 0
- **Precision:** 100.0%
- **Recall:** 100.0%

✅ Precision ≥ 90%
✅ Recall ≥ 80%

### no-temporary-monitoring

- **Total cases:** 25
- **True positives:** 13
- **False positives:** 0
- **True negatives:** 12
- **False negatives:** 0
- **Precision:** 100.0%
- **Recall:** 100.0%

✅ Precision ≥ 90%
✅ Recall ≥ 80%

## Final Decision Results (Manifest-Honouring Judge)

### no-domain-leak

- **Total cases:** 28
- **True positives (confirmed):** 13
- **False positives:** 0
- **True negatives (rejected):** 15
- **False negatives:** 0
- **Precision:** 100.0%
- **Recall:** 100.0%

### no-temporary-monitoring

- **Total cases:** 25
- **True positives (confirmed):** 12
- **False positives:** 0
- **True negatives (rejected):** 13
- **False negatives:** 0
- **Precision:** 100.0%
- **Recall:** 100.0%

## Assessment Incomplete Counts (coverage gaps / source unavailable)

- **no-domain-leak:** 1 incomplete case(s)
- **no-temporary-monitoring:** 0 incomplete case(s)

## Summary

This evaluation runs every case through the production ReviewEngine
with a path-and-SHA-sensitive adapter and manifest-honouring judge.
Candidate detection and final judgment are independently validated.
Assessment-incomplete counts are tracked separately.
All fixture files are saved on disk (no inline strings).

### Special cases exercised:
- `dl-pos-013`: renamed file (old → new path in diff header)
- `dl-pos-014`: candidate-positive case with final reject (reject judge exercised)
- `tm-pos-013`: candidate-positive monitoring case with final reject
- `dl-neg-004`: non-1 hunk offset (diff starts at line 3)
- `tm-pos-011`: disjoint hunks (two @@ sections in diff)
- `dl-neg-013`: large source/patch (≥20 KiB)
- `dl-neg-014`: Java 21 record pattern syntax
- `dl-neg-015`: over-production-limit source + patch (>100 KB source, >200 KB patch)

Report generated from 54 manifest-driven corpus cases.