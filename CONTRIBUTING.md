# Contributing to Invariant Guardian

Thank you for helping improve Invariant Guardian. This project values small, reviewable changes and a clear product boundary.

## Development setup

Invariant Guardian requires **Python 3.12** or newer.

```bash
git clone https://github.com/shahibag/architecture-invariant-guardian.git
cd architecture-invariant-guardian
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Running checks

Run the full verification set before opening a pull request:

```bash
python -m pytest -o addopts=''
python -m ruff check src/ tests/
python -m mypy src/
python -m pip check
git diff --check
docker build --no-cache -t invariant-guardian:local .
```

## Test expectations

- All existing tests must pass.
- New behavior must include tests at the appropriate layer:
  - Unit tests for parsing, scope matching, and domain models.
  - Engine tests through `ReviewEngine.assess` using in-memory adapters.
  - Contract tests for the `LLMJudge` and `SourceReader` ports.
  - Integration tests with saved GitHub HTTP fixtures for the Action runner.
- The 53-case offline regression corpus under `tests/evaluation/` must continue to meet its thresholds (candidate precision ≥ 90%, recall ≥ 80% per invariant).

## Evaluation fixtures

- Add new corpus cases to `tests/evaluation/manifest.yaml`.
- Each case needs a stable ID, expected candidate/final decision, Java syntax note, fixture paths, and rationale.
- Keep fixture files on disk; avoid inline Java or diff strings in test code.
- Update `tests/evaluation/reports/evaluation.md` and `evaluation.json` after running the corpus.

## Scope discipline

Invariant Guardian is intentionally narrow:

- Version 0.2 supports only `no-domain-leak` and `no-temporary-monitoring` for Java/Spring.
- Detectors must be deterministic and based on parsed structure, not unrestricted regex.
- The LLM judge may only confirm or reject candidates produced by deterministic detection.
- The Action never executes target Java code.
- Do not add new languages, invariants, autonomous fixes, dashboards, or merge-blocking behavior without prior discussion.

## Pull request process

1. Open a feature or fix branch from the latest `main`.
2. Make focused commits with clear messages.
3. Run the verification commands above.
4. Open a pull request and confirm the full CI run is green.
5. Request review from the maintainer.

## Code style

- Format and lint with Ruff.
- Type-check with mypy.
- Prefer explicit, safe error handling over broad exception catching.
- Keep comments factual and concise.

## Reporting issues

For bugs or feature requests, open a GitHub issue with:

- A minimal reproduction or fixture.
- Expected and actual behavior.
- The Invariant Guardian version or commit SHA.

For security issues, see [`SECURITY.md`](SECURITY.md) and report privately.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
