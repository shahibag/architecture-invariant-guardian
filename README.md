# Invariant Guardian

Invariant Guardian is a Python GitHub Action for repository-owned architecture invariant checks on Java/Spring pull requests.

It is not a general code-review bot. A finding must map to an invariant declared in `.guardian/invariants/`, cite changed-code evidence, and explain the architectural consequence. Human review remains the final decision.

## Current slice

The first runnable slice loads Markdown invariants and scans unified Java diffs for high-signal candidates related to:

- temporary monitoring, polling, or wait-retry workarounds;
- public boundaries that expose likely persistence/domain types.

Candidates are intentionally conservative. The evidence judge uses the OpenAI Python SDK against an OpenAI-compatible Chat Completions endpoint; the default is DeepSeek V4 Flash. Its live end-to-end verification remains pending a configured provider key.

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
      # actions/checkout@v4
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
      - uses: shahibag/architecture-invariant-guardian@v0.2.0
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          llm-api-key: ${{ secrets.DEEPSEEK_API_KEY }}
          llm-base-url: https://api.deepseek.com
          model: deepseek-v4-flash
```

> **Note:** `shahibag/architecture-invariant-guardian@v0.2.0` is an immutable
> point-release reference that becomes available only after the v0.2.0 release
> is published.  Until then, use a branch or commit SHA.

Fork pull requests do not use the provider key and do not publish a comment.

## Provider configuration

The Action uses the OpenAI Python SDK, but the endpoint and model are inputs. The default configuration is DeepSeek V4 Flash:

| Input | Default |
| --- | --- |
| `llm-base-url` | `https://api.deepseek.com` |
| `model` | `deepseek-v4-flash` |
| `llm-api-key` | no default; pass a GitHub Actions secret |

For OpenAI, set `llm-base-url` to `https://api.openai.com/v1` and select a Chat Completions-compatible model. The adapter requests JSON mode and always validates the response locally with Pydantic before publishing a finding.

### Secret storage

- **Local development:** create `.env.local` in the repository and store `LLM_API_KEY=...`; this file is ignored by Git. Restrict it to your user account (`chmod 600 .env.local`).
- **GitHub Actions:** add `DEEPSEEK_API_KEY` as a repository or organization Actions secret, then pass it through `llm-api-key`. Never put a key in `action.yml`, a workflow file, Docker build arguments, commit history, or logs.

Copy .env.local.example to .env.local for the local variable names. The action runner also accepts LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL when invoked outside GitHub Actions.

## End-to-end verification

Follow the [end-to-end test plan](docs/end-to-end-test-plan.md) using two private repositories: one for the Action and one Java/Spring demo repository. It covers confirmed violations, clean changes, idempotency, fork safety, and provider failures.
