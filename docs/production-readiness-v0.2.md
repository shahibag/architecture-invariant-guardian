# Invariant Guardian v0.2 — Production-Readiness Specification and Delivery Plan

## 1. Purpose

This document defines the work required to move Invariant Guardian from a demonstrated MVP to a production-pilot-quality architecture assessment for Java/Spring pull requests.

The current MVP is genuinely end to end: it has detected a temporary-monitoring violation, detected a domain-entity leak, produced a clean result for a safe DTO-style change, and updated an existing comment after remediation. Version 0.2 must make those results bounded, reproducible, measurable, and safe enough for controlled use on real repositories.

Version 0.2 remains an **advisory architecture assessment**. It does not become a generic review agent, execute pull-request code, generate fixes, or block merges by itself.

## 2. Product Boundary

Invariant Guardian answers one question:

> Does this pull request violate a repository-owned architectural invariant that the Guardian explicitly supports and has evidence to evaluate?

Every confirmed finding must:

1. Reference a loaded invariant ID.
2. Reference an in-scope changed Java file and changed line range.
3. Reuse deterministic evidence gathered by the Guardian.
4. Explain the architectural consequence of that evidence.
5. Avoid generic style, testing, performance, naming, or refactoring advice.

The model may confirm or reject deterministic candidates. It must never invent candidates.

### Supported invariants

Version 0.2 continues to support only:

- `no-temporary-monitoring`
- `no-domain-leak`

Adding more invariants, languages, autonomous fixes, historical learning, dashboards, and ownership-map enforcement is outside this release.

## 3. Release Outcomes

Version 0.2 is complete only when all of the following are true:

- Invariant path scopes are enforced before detection.
- Model input is bounded and required omissions produce `assessment_incomplete`.
- Provider output contains exactly one valid decision per candidate or the assessment is incomplete.
- Java candidates are based on parsed Java structure rather than only line-level naming regexes.
- GitHub comments are updated only when owned by the Action bot.
- Public comments never contain raw exception text.
- The Action emits machine-readable status outputs for repository-owned policy decisions.
- A versioned evaluation corpus meets the release thresholds in section 12.
- The current code has passed unit, contract, integration, Docker, and live demo checks.
- A new immutable release is created; the existing `v0.1.0` tag is not moved again.

## 4. Non-Goals

- Compiling, importing, or executing code from a pull request.
- Replacing ArchUnit, compiler checks, tests, static analysis, or human architecture review.
- Proving arbitrary architecture properties across a complete Java repository.
- Supporting arbitrary custom detection logic described only in Markdown.
- Adding an Anthropic implementation before the existing provider contract has two real production adapters.
- Returning automated patches or committing changes to contributor branches.
- Making confirmed findings fail the workflow automatically.

Repositories that want enforcement can consume the Action outputs in their own policy step after the pilot proves acceptable precision.

## 5. Required Domain Contract

The application module exposes one primary interface:

```python
class ReviewEngine:
    def assess(self, request: ReviewRequest) -> Assessment: ...
```

The interface must hide path matching, patch parsing, Java parsing, context budgeting, candidate detection, provider judgment, and provider-output validation. The GitHub Action runner translates an event into `ReviewRequest`, calls the engine, publishes the result, and writes Action outputs.

Suggested domain models:

```python
class ReviewRequest(BaseModel):
    base_sha: str
    head_sha: str
    invariants: list[Invariant]
    changed_files: list[ChangedFile]

class ChangedFile(BaseModel):
    path: str
    status: Literal["added", "modified", "removed", "renamed"]
    patch: str | None
    patch_complete: bool

class Coverage(BaseModel):
    evaluated_files: list[str]
    skipped_files: list[CoverageGap]
    context_truncated: bool

class ProviderUsage(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    model: str
    prompt_version: str

class Assessment(BaseModel):
    status: AssessmentStatus
    candidates: list[CandidateFinding]
    violations: list[Violation]
    coverage: Coverage
    provider_usage: ProviderUsage | None
    warnings: list[SafeWarning]
```

`warnings` must contain safe categories and user-facing messages, never raw exception objects.

### Status precedence

1. If any in-scope Java change cannot be evaluated, required context is omitted, or judgment is invalid/unavailable, status is `assessment_incomplete`. Confirmed violations already established may still be retained and displayed.
2. Otherwise, if at least one candidate is confirmed, status is `confirmed_violations`.
3. Otherwise status is `no_confirmed_violations`.

Consequently, `no_confirmed_violations` always means the supported, in-scope changes were fully evaluated—not merely that no regex matched.

## 6. Repository Reader and Diff Contract

Replace the whole-diff input with changed-file records from GitHub's pull-request files endpoint.

The GitHub reader must:

- Paginate all changed files.
- Preserve file status and rename information.
- Record missing or truncated patches explicitly.
- Fetch invariant files only from the exact base SHA.
- Fetch candidate-related Java source only from the exact base or head SHA requested by the context selector.
- Refuse binary content and files above the configured source-size limit.
- Never check out, compile, import, or execute pull-request code.

Introduce a `SourceReader` port only because two adapters are required: the real GitHub adapter and an in-memory adapter for engine tests.

## 7. Scope and Context Selection

### Scope enforcement

Before detection, normalize repository-relative POSIX paths and match them against each invariant's `scope.languages` and `scope.include_paths`.

- Only `.java` files can match the `java` language in version 0.2.
- Path traversal, absolute paths, and invalid glob patterns invalidate that invariant.
- A file excluded from one invariant may still be included by another.
- Removed files do not create new violations but must not break patch line accounting.

### Fixed context budgets

Use code constants for version 0.2 instead of adding several public configuration inputs:

| Limit | Initial value |
| --- | ---: |
| Changed files | 200 |
| Patch bytes across in-scope Java files | 200,000 |
| Candidate count | 25 |
| Source bytes fetched per related file | 100,000 |
| Total model-context characters | 60,000 |
| Context lines around a candidate | 40 before and 40 after |

These are safety ceilings, not product guarantees. Record the applied limits in logs and evaluation metadata.

The model receives only:

- invariant text applicable to the candidate;
- normalized candidate records;
- candidate-specific changed hunks;
- bounded enclosing Java declaration context;
- bounded related-type evidence when required.

It does not receive unrelated files, PR descriptions, comments, commit messages, or the unbounded full diff.

If a limit prevents required in-scope evidence from being evaluated, record a coverage gap and return `assessment_incomplete`. Never silently drop candidates or return clean.

## 8. Java Analysis

### Parser decision gate

Before adopting a parser dependency, add a short compatibility spike covering Java 17 and Java 21 syntax used in fixtures: annotations, records, generics, nested classes, multiline method declarations, lambdas, switch expressions, and text blocks.

Prefer a Python-accessible Tree-sitter Java parser if its Python 3.12 wheels and target syntax pass the spike. Do not invoke Maven, Gradle, `javac`, annotation processors, or repository build scripts. If the parser gate fails, stop the AST phase and document the result rather than falling back to broad regex claims.

Regex remains acceptable only for parsing unified patch markers and as a conservative fallback signal; it must not be the sole evidence for a confirmed architecture type relationship.

### Domain-leak detector

A candidate requires both a supported public boundary and evidence about the exposed type.

Supported public boundaries:

- Class or method annotated with Spring web annotations such as `@RestController`, `@Controller`, `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@PutMapping`, `@PatchMapping`, or `@DeleteMapping`.
- A public method in a repository path explicitly included by the invariant and designated as a public contract in the invariant's examples or future documented configuration. Version 0.2 should not infer every public service method as an API boundary.

Supported internal-type evidence:

- `@Entity`, `@MappedSuperclass`, or `@Embeddable` on the referenced declaration.
- A supported internal naming convention (`Entity`, `PersistenceModel`, or `Aggregate`) when the relevant type declaration is also supplied to the judge.

Inspect method return types and parameter types, including generic container element types. Dedicated DTOs, Java records used as response contracts, and explicitly public contract types must remain acceptable cases.

### Temporary-monitoring detector

Detect structural additions of:

- Spring `@Scheduled` methods;
- `ScheduledExecutorService` scheduling calls;
- unbounded polling loops;
- retry loops containing sleep or backoff calls.

State-change evidence must come from the same changed method, enclosing declaration, or explicitly related changed flow—not from an unrelated line elsewhere in the PR. The context passed to the judge must include enough enclosing code to distinguish a workaround from an intentional periodic business process or bounded resilience policy.

## 9. Judge Contract

Use the OpenAI Python SDK with a configurable OpenAI-compatible base URL and model. DeepSeek remains the demonstrated default. Do not add another provider SDK in version 0.2.

Replace `confirm(invariants, candidates, diff)` with:

```python
class LLMJudge(Protocol):
    def evaluate(self, request: JudgeRequest) -> JudgeResult: ...
```

`JudgeRequest` contains only bounded context and candidate IDs. `JudgeResult` contains candidate decisions and usage metadata.

### Output validation

For `N` candidates, a valid provider result must contain:

- exactly `N` decisions;
- every index from `0` through `N - 1` exactly once;
- only `confirm` or `reject` decisions;
- bounded explanation and suggested-direction strings;
- no unknown candidate index.

Missing, duplicate, or unknown indexes make the assessment incomplete. They must never be interpreted as rejection or a clean result.

### Failure behavior

Classify provider failures as:

- `authentication_error`
- `rate_limited`
- `timeout`
- `provider_unavailable`
- `invalid_response`
- `internal_error`

Use an explicit request timeout. Permit at most one retry for timeouts, rate limits, and provider 5xx responses. Do not retry authentication failures or schema-validation failures.

The public comment uses only a safe message such as `AI judgment was unavailable (provider_unavailable)`. Detailed diagnostics may be logged only after removing request bodies, response bodies, headers, URLs containing credentials, and source code.

Record provider-reported input/output token usage when available. Do not calculate monetary cost inside the Action because provider pricing changes independently of the release.

Version the prompt with a constant such as `PROMPT_VERSION = "guardian-judge-v2"` and include it in evaluation records.

## 10. GitHub Publication and Action Interface

### Bot-owned comment

The publisher must:

- Find only comments containing the Guardian marker and authored by `github-actions[bot]` for the current GitHub Actions implementation.
- Paginate comments until the owned comment is found or all pages are exhausted.
- Never patch a contributor-authored comment, even when it contains a copied marker.
- Maintain one versioned marker, for example `<!-- invariant-guardian:v2:<fingerprint> -->`.
- Avoid an update when the complete rendered body is unchanged.

### Rendered result

The comment must separately communicate:

- assessment status;
- confirmed violations;
- incomplete coverage or provider failure;
- evaluated/skipped in-scope file counts;
- the human-review advisory statement.

When confirmed violations and incomplete coverage coexist, show both. Do not render raw exceptions, full prompts, token values, or unrelated source.

### Action outputs

Add outputs to `action.yml` and write them through `GITHUB_OUTPUT`:

| Output | Values |
| --- | --- |
| `assessment-status` | `no_confirmed_violations`, `confirmed_violations`, or `assessment_incomplete` |
| `confirmed-count` | non-negative integer |
| `candidate-count` | non-negative integer |
| `coverage-complete` | `true` or `false` |

The Action remains successful for a completed advisory assessment regardless of confirmed violations. Unexpected internal failures that prevent creating any assessment should fail the step. Consuming repositories may enforce their own policy based on outputs after the pilot phase.

### Fork pull requests

On fork pull requests:

- Do not send provider requests.
- Do not assume write permission for comments.
- Emit a safe `assessment_incomplete` result to logs and Action outputs when possible.
- Never expose repository secrets.

## 11. Security Requirements

- Treat PR patches, source files, invariant prose, provider output, and GitHub comments as untrusted input.
- Load invariants from the exact base SHA only.
- Never execute target-repository code.
- Never write API keys to files, build arguments, output fields, comments, or logs.
- Pin third-party workflow actions to full commit SHAs in production examples.
- Cap HTTP response sizes before decoding them.
- Validate repository paths before local temporary-file writes.
- Use least-privilege workflow permissions: `contents: read` and `pull-requests: write`.
- Document that configured model providers receive selected source context.
- Add prompt-injection cases in comments, string literals, Java comments, and invariant examples; none may alter the judge contract or invent findings.

## 12. Evaluation Specification

Create a versioned corpus under `tests/evaluation/manifest.yaml`. Every case contains:

- stable case ID;
- invariant ID;
- expected candidate and final decision;
- Java version/syntax feature;
- fixture paths;
- expected evidence location;
- rationale for the expected result;
- whether live judgment is required.

### Minimum corpus

At least 48 cases total:

- 12 positive and 12 negative/allowed cases for temporary monitoring;
- 12 positive and 12 negative/allowed cases for domain leakage.

Cases must include multiline signatures, annotations, generics, records, nested types, unrelated state changes, intentional scheduled jobs, bounded resilience retries, DTOs, public events, JPA annotations, naming-convention mismatches, renamed files, large patches, and prompt-injection text.

### Offline release thresholds

- Candidate precision at least 90% per invariant.
- Candidate recall at least 80% per invariant for the explicitly supported pattern matrix.
- Evidence file and changed-line validity: 100%.
- Unsupported provider decisions accepted as clean: 0.
- Provider/schema/context failures reported as incomplete: 100%.
- Contributor-marker comments modified: 0.

Record results as machine-readable JSON and a concise Markdown summary. Never claim recall over arbitrary Java architecture violations; the denominator is the documented supported corpus.

### Pilot thresholds

Run in advisory mode on at least 50 representative pull requests across one or more consenting Java/Spring repositories.

- Manually label each finding as useful, incorrect, or ambiguous.
- Target useful-finding precision of at least 90% before offering merge-gate guidance.
- Track incomplete assessments separately from clean results.
- Record median and p95 runtime, provider input/output tokens, changed-file counts, and coverage gaps.
- Treat any secret disclosure, PR-code execution, unsupported invented finding, or false clean caused by system failure as a release blocker.

## 13. Verification Layers

### Unit tests

- Invariant parsing and invalid glob handling.
- Scope matching and path normalization.
- Patch parsing and changed-line mapping.
- Java AST fact extraction.
- Context budgets and truncation.
- Exact provider-decision coverage.
- Safe error classification and rendering.
- Fingerprinting and outputs.

### Contract tests

- `LLMJudge` with valid, missing, duplicate, unknown-index, empty, malformed, and oversized responses.
- `SourceReader` with normal, missing, oversized, binary, renamed, and unavailable files.
- Publisher with bot-owned, contributor-spoofed, duplicate, paginated, unchanged, and stale comments.

### Engine tests

Test through `ReviewEngine.assess` using in-memory adapters. Assert observable assessment status, violations, evidence, coverage, and safe warnings. Avoid tests that depend on private helper structure.

### CI integration tests

- Saved GitHub event and HTTP response fixtures exercise the full Action runner without external calls.
- Docker image builds and the packaged command runs a fixture assessment.
- Python 3.12 tests, Ruff, and a static type checker pass.
- Dependency audit runs and reports actionable vulnerabilities.

### Live end-to-end tests

Use `guardian-java-demo` and retain run URLs for:

1. Monitoring violation confirmed.
2. Domain leak confirmed.
3. Safe DTO/public contract rejected as a candidate or judged clean.
4. Remediation updates the existing comment to clean.
5. Unchanged rerun creates no duplicate comment.
6. Contributor posts a copied marker; Guardian does not edit it.
7. Invalid provider key produces incomplete, not clean.
8. Real fork PR does not receive secrets or invoke the model.
9. Deliberately oversized in-scope patch produces incomplete coverage.

Use the smallest possible live fixtures and no more than one model request per deliberate candidate scenario.

## 14. Delivery Plan

Each phase should be one reviewable pull request or a short, cohesive sequence of commits. Do not begin the next phase until the current phase passes its acceptance checks.

### Phase 1 — Correctness and bounded assessment

Required work:

- Add the revised domain models and `ReviewEngine` interface.
- Enforce language/path scopes.
- Replace whole-diff judging with bounded candidate context.
- Add coverage tracking and status precedence.
- Require an exact provider decision for every candidate.
- Sanitize provider failures and add explicit timeout/retry behavior.
- Add Action outputs.

Acceptance:

- No oversized, missing, or invalid provider/context case returns clean.
- Existing three positive/clean fixture behaviors remain correct.
- Unit, engine, and provider-contract tests pass.

### Phase 2 — Java structural analysis

Required work:

- Complete and document the Java-parser compatibility gate.
- Add AST fact extraction without compiling or executing source.
- Implement the revised domain-leak and temporary-monitoring contracts.
- Fetch bounded related-type source when domain-type evidence requires it.
- Build the 48-case corpus.

Acceptance:

- Parser fixtures cover the selected Java 17/21 syntax.
- Offline evaluation meets the thresholds in section 12.
- Findings cite valid changed locations and deterministic evidence.

### Phase 3 — GitHub and release hardening

Required work:

- Paginate changed files and comments.
- Verify bot ownership before updating comments.
- Handle missing/truncated patches and bounded HTTP responses.
- Add saved-response integration tests.
- Add Docker smoke testing, linting, typing, and dependency auditing to CI.
- Update examples to pin third-party actions and Guardian releases immutably.

Acceptance:

- Contributor marker-spoof tests pass.
- Docker and Action-runner integration tests pass in CI.
- The source repository is clean and all checks pass from a fresh environment.

### Phase 4 — Live verification and documentation

Required work:

- Run the nine live scenarios in `guardian-java-demo`.
- Record run URLs, outcomes, latency, and token usage in a dated evaluation report.
- Correct stale README statements and document the measured support matrix.
- Add an ADR covering advisory outputs versus repository-owned enforcement.
- Create a new immutable semantic release, preferably `v0.2.0`, only after all release gates pass.

Acceptance:

- All required live scenarios have retained evidence.
- No tag used as an immutable point release is moved after publication.
- Documentation makes no broader claim than the measured corpus and pilot evidence support.

### Phase 5 — Controlled pilot

Required work:

- Enable advisory mode on consenting Java/Spring repositories.
- Label outcomes and collect the pilot metrics in section 12.
- Tune only documented detectors and fixtures; do not give the model free-form review authority.

Acceptance:

- At least 50 representative PR assessments are labeled.
- Useful-finding precision is at least 90%.
- The team can decide, from evidence, whether a separate consuming workflow should block on selected invariant severities.

## 15. Suggested File Changes

Claude should adapt names to existing conventions and avoid duplicating modules, but the expected responsibility map is:

```text
src/invariant_guardian/
├── action_runner.py                 # GitHub event translation, publication, outputs
├── application.py                   # ReviewEngine and orchestration
├── domain/models.py                 # request, assessment, coverage, usage, safe errors
├── ports.py                         # LLMJudge and SourceReader seams
├── context.py                       # scope matching and bounded candidate context
├── rules/java.py                    # detector orchestration
├── rules/java_ast.py                # Java fact extraction
├── adapters/github/client.py        # paginated reader and bot-owned publisher
├── adapters/openai/judge.py         # compatible provider adapter
└── rendering/comment.py             # safe human result

tests/
├── evaluation/
├── fixtures/github/
├── fixtures/java/
├── test_engine.py
├── test_context.py
├── test_java_ast.py
├── test_github_client.py
└── test_openai_judge.py
```

The final structure may remain flatter if that keeps the interface smaller. Do not add a generic detector plugin framework or a second provider adapter in anticipation of future needs.

## 16. Claude Execution Instructions

Provide Claude with this document and the two repository URLs/checkouts, then use the following instruction:

> Implement `docs/production-readiness-v0.2.md` phase by phase in `architecture-invariant-guardian`, using `guardian-java-demo` only for the specified live verification. Preserve the product boundary: two Java invariants, deterministic candidates, constrained OpenAI-compatible judgment, and advisory output. Start by auditing current code against Phase 1 and writing failing tests. Keep each phase reviewable and run all relevant tests, lint, typing, and Docker checks before proceeding. Do not execute demo-repository PR code. Do not expose or print secrets. Do not move `v0.1.0`; create `v0.2.0` only after every release gate passes and only with explicit authorization to publish. Do not add Anthropic, generic plugins, dashboards, autonomous fixes, or merge blocking. Record deviations and unresolved risks instead of silently changing the specification.

### Authorization checklist for the user

Before Claude performs external mutations, explicitly decide whether it may:

- push branches to both repositories;
- open, update, or close demo pull requests;
- consume the configured DeepSeek secret for the bounded live cases;
- create the GitHub release and immutable `v0.2.0` tag;
- enable the Action on any repository beyond `guardian-java-demo`.

Local implementation and tests do not require those external permissions.

## 17. Definition of Production Value

Version 0.2 has real production value when it reliably catches the explicitly supported architecture regressions with evidence, stays quiet on documented acceptable patterns, fails visibly when coverage or judgment is incomplete, and gives a Java team enough measured precision to keep it enabled in advisory mode.

It should not be described as a general Java architecture verifier. Its defensible claim is:

> Invariant Guardian is an evaluated GitHub Action that checks changed Java/Spring code against repository-owned architecture invariants using bounded deterministic evidence and constrained model judgment, without executing pull-request code.
