# Invariant Guardian — Implementation-Ready MVP Specification

## 1. Product Definition

**Invariant Guardian** is a Python GitHub Action that assesses whether a Java/Spring pull request violates architectural invariants owned by that repository.

It is deliberately **not** a general code-review bot. It does not comment on naming, style, broad performance, test coverage, or generic refactoring opportunities. Every published finding must map to a repository-owned invariant, cite supplied code evidence, and state the architectural consequence.

### MVP outcome

On an eligible pull request, the Action reads Markdown invariant files from the base repository, analyzes changed Java/Spring code, and updates one human-reviewable **Invariant Assessment** comment. A human decides whether to fix, justify, or acknowledge a finding. The Action never blocks a merge solely because it found a possible violation.

## 2. Fixed Technical Decisions

| Area | MVP decision |
| --- | --- |
| Product name | Invariant Guardian |
| Runtime | Python 3.12 Docker-based GitHub Action |
| Target code | Java/Spring pull requests only |
| Primary model provider | OpenAI Python SDK using the Responses API |
| Model configuration | Configurable Action input; pin a specific model snapshot for evaluation runs |
| Structured result | Provider output is validated against a local Pydantic schema |
| Future provider support | A provider-neutral `LLMJudge` port permits a later Anthropic adapter; no Anthropic SDK in the MVP |
| Invariant format | One Markdown file per invariant under `.guardian/invariants/` |
| Enforced rules | Temporary monitoring/retry workarounds and domain/persistence leakage |
| Publication | One idempotently updated GitHub PR comment |

## 3. Non-goals

- Generic AI code review.
- Automated fixes, merge approval, merge blocking, or code execution from the PR.
- YAML invariants, free-form `ARCHITECTURE.md` parsing, TypeScript/Python source analysis, dashboards, historical learning, or acknowledgment tracking.
- Enforcing cross-cutting ownership before a repository provides an explicit ownership map.

## 4. Invariant Contract

Each target repository owns Markdown files at `.guardian/invariants/*.md`. The Action loads invariant files from the base commit, never from untrusted PR changes.

```markdown
---
id: no-temporary-monitoring
title: No temporary monitoring or retry loops masking a root-cause fix
severity: error
scope:
  languages: [java]
  include_paths: ["src/main/java/**"]
---

## Rule
...

## Rationale
...

## Violating examples
...

## Acceptable examples
...
```

Required front matter:

- `id`: stable, unique, kebab-case identifier.
- `title`: human-readable name.
- `severity`: `error` or `warning`.
- `scope.languages`: must include `java` for this MVP.
- `scope.include_paths`: one or more glob patterns.

Required sections are `Rule`, `Rationale`, `Violating examples`, and `Acceptable examples`. Malformed or unsupported files produce an informational run status and are excluded from evaluation.

## 5. Enforced Invariants

### 5.1 No temporary monitoring or retry loops

**Intent:** do not introduce polling, scheduling, or waiting retries merely to hide a missing event, incorrect state transition, or downstream design problem.

**Deterministic candidate signals:** newly added `@Scheduled`, `ScheduledExecutorService`, polling queries, state-wait loops, or retry loops containing sleep/backoff.

**Confirmation requirement:** the Action must show the newly added mechanism and contextual evidence that the same pull request changes the business state or flow being watched. A signal alone is not a published violation.

**Allowed examples:** a documented periodic business process such as reconciliation; bounded retry policy owned by a dedicated resilience component with an explicit failure path; a scheduler explicitly defined as the source of truth for the business process.

### 5.2 No internal domain or persistence leakage

**Intent:** public APIs and module boundaries must not expose JPA entities, persistence models, or internal domain types.

**Deterministic candidate signals:** changed public controllers, facades, events, or module APIs whose request, response, return, or parameter types match known persistence/domain conventions or annotations.

**Confirmation requirement:** the Action must identify the public boundary, the exposed type, and evidence that the type is internal or persistence-backed in supplied context.

**Allowed examples:** dedicated request/response DTOs, deliberately published integration events, and API types explicitly declared as public contracts.

## 6. Review Pipeline

1. **GitHub reader** fetches PR metadata, changed-file patches, and base-commit invariant files through the GitHub API.
2. **Context selector** fetches the full diff but sends only selected changed hunks and bounded related context to the model. It records truncation and never claims full evaluation after required evidence is omitted.
3. **Deterministic detectors** emit candidate findings with invariant ID, file, changed line range, pattern, and evidence.
4. **LLM judge** receives only loaded invariants, bounded context, and candidate findings. It may confirm, reject, or lower confidence for candidates; it must not invent unrelated review categories.
5. **Validator** parses the provider response into Pydantic models and rejects findings whose invariant ID, file, or line range cannot be verified against supplied context.
6. **Comment publisher** updates one bot-owned PR comment grouped by invariant.

The output states one of three outcomes: `no confirmed violations`, `confirmed violations`, or `assessment incomplete`. A provider failure, malformed response, or truncated required evidence produces `assessment incomplete`, never a clean result.

## 7. Provider Contract

The application depends on a small provider-neutral port:

```python
class LLMJudge(Protocol):
    def evaluate(self, request: JudgeRequest) -> JudgeResult: ...
```

`JudgeRequest` contains validated invariants, bounded context, and deterministic candidates. `JudgeResult` contains only confirmed or rejected candidates plus token-usage metadata. `OpenAIJudge` is the only MVP adapter. A future `AnthropicJudge` must satisfy the same contract and pass the same contract tests.

The OpenAI API key is provided only through `OPENAI_API_KEY`; it is not written to logs, comments, artifacts, or exceptions.

## 8. Security and Execution Policy

- The Action does not run, import, build, or test PR code.
- PR diff text, source code, pull-request metadata, and comments are untrusted data, never instructions. The system prompt and invariant contract take precedence.
- The workflow uses the GitHub API rather than checking out untrusted PR code for analysis.
- The least required permissions are `contents: read` and `pull-requests: write` for the one summary comment.
- AI assessment runs only in trusted repository contexts where `OPENAI_API_KEY` is available. Fork pull requests receive deterministic analysis only and an explicit AI-skipped status.
- No source code or secrets are persisted outside GitHub and the configured model provider. Logs contain counts, durations, outcome, and safe error categories only.
- One retry is permitted for a transient model request failure; no retry occurs for schema validation or authentication failures.

## 9. Comment and Idempotency Contract

The Action owns one PR comment identified by a hidden marker. It derives a finding fingerprint from the base SHA, head SHA, invariant IDs, file paths, line ranges, and normalized evidence. If the fingerprint is unchanged, it leaves the comment untouched; otherwise it updates the existing comment instead of creating another.

Each confirmed finding contains:

- invariant title and ID;
- changed location;
- why the architecture rule matters;
- concise evidence;
- a constructive direction, not an automatic fix;
- confidence.

## 10. Repository Plan

```text
invariant-guardian/
├── action.yml
├── Dockerfile
├── pyproject.toml
├── src/invariant_guardian/
│   ├── domain/          # Pydantic models and stable contracts
│   ├── application/     # review orchestration
│   ├── ports/           # GitHub reader, judge, publisher, logger
│   ├── adapters/github/
│   ├── adapters/openai/
│   ├── rules/java/
│   └── rendering/
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── contract/
│   └── integration/
├── examples/java-spring-service/
├── docs/
│   ├── implementation-ready-mvp.md
│   └── Architecture-Invariant-Guardian-Design.md
└── README.md
```

The architecture has only boundaries required today: domain contracts, application orchestration, ports, and adapters. It does not introduce a generic plugin platform.

## 11. Delivery Slices

### Slice 1: Local policy and deterministic assessment

- Scaffold the Python package, Docker Action metadata, and test setup.
- Load and validate Markdown invariant files.
- Implement the temporary-monitoring detector.
- Add clean, violating, and allowed-exception fixtures.
- Render an assessment locally without calling GitHub or OpenAI.

**Done when:** fixture tests pass and the renderer distinguishes confirmed candidate, clean, and incomplete outcomes.

### Slice 2: GitHub Action integration

- Add GitHub API reader and idempotent comment publisher.
- Use saved API fixtures for integration tests.
- Add a sample Java/Spring repository and workflow documentation.

**Done when:** a test pull request updates one stable assessment comment without executing PR code.

### Slice 3: OpenAI evidence judgment

- Implement `OpenAIJudge` with structured output and Pydantic validation.
- Add prompt-injection, malformed-response, timeout, and missing-key tests.
- Add token, latency, and outcome logging.

**Done when:** the model can confirm or reject deterministic candidates without creating unsupported findings.

### Slice 4: Domain-leak detector and portfolio evidence

- Implement the second detector and its fixture matrix.
- Run the full curated evaluation set using a pinned model snapshot.
- Record precision, false positives, incomplete runs, latency, and model usage.
- Create the demonstration: bad PR, evidence-cited assessment, corrected PR with no finding.

**Done when:** the README and portfolio claim only measured, repeatable behavior.

## 12. Acceptance Criteria

- No published finding lacks a loaded invariant ID and verifiable supplied-code evidence.
- Clean and explicitly acceptable fixtures do not receive violation comments.
- Fork PRs never expose the OpenAI key.
- Model failures are reported as incomplete assessment, not as clean reviews.
- Re-running the same PR does not create duplicate comments.
- The Action does not execute PR code.
- All claimed portfolio metrics come from the curated fixture evaluation.
