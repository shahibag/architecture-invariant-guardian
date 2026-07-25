# Invariant Guardian

Invariant Guardian is a Python GitHub Action for repository-owned architecture invariant checks on Java/Spring pull requests.

It is not a general code-review bot. A finding must map to an invariant declared in `.guardian/invariants/`, cite changed-code evidence, and explain the architectural consequence. Human review remains the final decision.

## Current slice

The first runnable slice loads Markdown invariants and scans unified Java diffs for high-signal candidates related to:

- temporary monitoring, polling, or wait-retry workarounds;
- public boundaries that expose likely persistence/domain types.

Candidates are intentionally conservative. OpenAI evidence judgment and GitHub comment publishing remain the next slices, pending secure OpenAI Platform reauthentication.

## Local use

```bash
python -m pip install -e '.[dev]'
invariant-guardian assess \
  --invariants tests/fixtures/invariants \
  --diff tests/fixtures/temporary_monitoring.diff
```

## Repository invariant format

See [the implementation-ready MVP specification](docs/implementation-ready-mvp.md) for the required Markdown format, execution policy, and delivery plan.

