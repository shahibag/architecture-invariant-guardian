# Invariant Guardian

Invariant Guardian is a Python GitHub Action for repository-owned architecture invariant checks on Java/Spring pull requests.

It is not a general code-review bot. A finding must map to an invariant declared in `.guardian/invariants/`, cite changed-code evidence, and explain the architectural consequence. Human review remains the final decision.

## Current slice

The first runnable slice loads Markdown invariants and scans unified Java diffs for high-signal candidates related to:

- temporary monitoring, polling, or wait-retry workarounds;
- public boundaries that expose likely persistence/domain types.

Candidates are intentionally conservative. The OpenAI evidence-judge and GitHub comment adapters are implemented behind stable ports; their live end-to-end verification remains pending secure OpenAI Platform reauthentication.

## Local use

```bash
python -m pip install -e '.[dev]'
invariant-guardian assess \
  --invariants tests/fixtures/invariants \
  --diff tests/fixtures/temporary_monitoring.diff
```

## Repository invariant format

See [the implementation-ready MVP specification](docs/implementation-ready-mvp.md) for the required Markdown format, execution policy, and delivery plan.

## GitHub Action use

Target repositories should run the Action on `pull_request` and grant only the permissions it needs:

```yaml
name: Invariant Guardian

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  assess:
    runs-on: ubuntu-latest
    steps:
      - uses: your-org/invariant-guardian@v0
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          openai-api-key: ${{ secrets.OPENAI_API_KEY }}
          model: gpt-5.6-terra
```

Fork pull requests do not use the OpenAI key and do not publish a comment.
