# Invariant Guardian

Invariant Guardian is a Python GitHub Action for repository-owned architecture invariant checks on Java/Spring pull requests.

It is not a general code-review bot. A finding must map to an invariant declared in `.guardian/invariants/`, cite changed-code evidence, and explain the architectural consequence. Human review remains the final decision.

## Current release line (v0.2)

Version 0.2 is an advisory architecture assessment GitHub Action for Java/Spring pull requests. It supports exactly two repository-owned invariants:

- `no-temporary-monitoring`
- `no-domain-leak`

Deterministic Java AST analysis produces candidates. An OpenAI-compatible evidence judge (default DeepSeek V4 Flash) may only confirm or reject those candidates. The Action never executes pull-request code and never blocks merges by itself.

Package version: `0.2.0`. The immutable git tag `v0.2.0` is created only after this line is merged and release gates pass — until then, pin a commit SHA or branch ref.

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


## Known limitations (v0.2)

- Only the two supported invariant IDs above have detectors. Unsupported or duplicate IDs return `assessment_incomplete` rather than a false clean result.
- Public helper methods on `@RestController` / `@Controller` classes are treated as public boundaries even without a method-level `@*Mapping` annotation. Tighten this in v0.3 if controller noise is too high.
- Cross-module type resolution uses a bounded Git tree scan (entry and root caps). Failed or over-budget extra-root discovery no longer disables same-module primary-root resolution, but very large monorepos may still mark some cross-module leaks incomplete.
- Nested generic leaves, overload identity, and Aggregate/PersistenceModel naming without JPA are supported for the advertised patterns; broader Java architecture claims are out of scope.
- Live provider judgment is optional in CI. Provider failures always yield `assessment_incomplete`, never a false clean result.

## End-to-end verification

Follow the [end-to-end test plan](docs/end-to-end-test-plan.md) using two private repositories: one for the Action and one Java/Spring demo repository. It covers confirmed violations, clean changes, idempotency, fork safety, and provider failures.
