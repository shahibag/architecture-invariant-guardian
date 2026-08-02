# Invariant Guardian v0.2 — Case Study

## 1. Problem

Java/Spring repositories accumulate architecture drift in small, reviewable pull requests. Two recurring failure modes:

- **Persistence entities leak through REST boundaries.** A controller starts returning `OrderEntity` directly, or `ResponseEntity<List<OrderEntity>>`, coupling the public API to database schema and bypassing validation or projection logic.
- **Temporary monitoring masks root causes.** A scheduled retry loop or `ScheduledExecutorService` task papers over an unprocessed-order problem instead of fixing the underlying failure.

Generic linters cannot express repository-specific intent like these. Human architecture review is easy to skip under pressure. And unrestricted LLM review may hallucinate findings or cite evidence that was not changed.

## 2. Product boundary

Invariant Guardian v0.2 is an **advisory** GitHub Action for Java/Spring pull requests. It:

- Supports exactly two repository-owned invariants: `no-domain-leak` and `no-temporary-monitoring`.
- Detects candidates with deterministic Java AST analysis (Tree-sitter).
- Confirms or rejects each candidate with a constrained, evidence-bound LLM judge.
- Never compiles, imports, or executes target code.
- Never generates detectors from arbitrary Markdown or applies automated fixes.
- Loads invariants only from the exact base SHA and reads related source from exact commits.

## 3. Architecture

### Action event adapter

`action_runner.py` translates the GitHub `pull_request` event into a `ReviewRequest`, detects fork PRs, handles provider configuration from inputs/secrets, and writes Action outputs.

### Exact-SHA GitHub reader

`adapters/github/client.py` paginates the changed-files endpoint, records patch completeness, decodes Base64 contents (including newline-wrapped GitHub variants), and fetches invariant files and related Java source from precise base or head SHAs.

### Invariant loader

`invariants.py` parses Markdown invariant files, validates scope (`languages`, `include_paths`), execution policy, and examples, and rejects unsupported or duplicate IDs before detection.

### Scope and coverage accounting

`context.py` normalizes repository-relative paths, matches them against invariant scopes, and applies fixed budgets: changed files, patch bytes, candidate count, source bytes per related file, and total model-context characters. Every truncation or omission becomes a coverage gap.

### Tree-sitter parser

`rules/java_ast.py` extracts Java facts with Tree-sitter: annotations, return types, parameter types, generic element types, enclosing declarations, and overload identity. No compiler or build tool is invoked.

### Deterministic detectors

`rules/java.py` runs the two supported detectors:

- `no-domain-leak` identifies public Spring boundaries and checks whether they expose internal types.
- `no-temporary-monitoring` identifies `@Scheduled` methods, `ScheduledExecutorService` scheduling, polling loops, and retry loops with sleep/backoff.

### Evidence builder

`context.py` assembles a bounded evidence package per candidate: the invariant text, the candidate record, the changed hunks, and bounded declaration context. Unrelated files, PR descriptions, and comments are excluded.

### LLM judge contract

`adapters/openai/judge.py` sends the evidence package to an OpenAI-compatible endpoint. The response must contain exactly one decision per candidate, only `confirm` or `reject`, and bounded explanation strings. The prompt is versioned (`guardian-judge-v2`).

### Schema validation

`domain/models.py` validates provider responses with Pydantic. Missing, duplicate, or unknown candidate indexes make the assessment incomplete.

### Rendering and publication

`rendering/comment.py` produces a safe, idempotent PR comment with a versioned marker. `adapters/github/client.py` finds only bot-owned comments and updates the existing one only when the rendered body changes.

### Action outputs

`action.yml` exposes `assessment-status`, `confirmed-count`, `candidate-count`, and `coverage-complete` through `GITHUB_OUTPUT`.

### Why separate deterministic detection and LLM judgment?

Deterministic detection grounds every candidate in parseable source structure and changed-line evidence. The LLM is then constrained to confirm or reject that specific evidence, which prevents invented findings. If the provider is unavailable, the system returns `assessment_incomplete` rather than a false clean result.

## 4. Hard engineering problems

- **Newline-wrapped GitHub Base64.** The Contents API sometimes returns Base64 with line breaks; the decoder normalizes them before decoding.
- **Pagination URL variants.** GitHub returns `repositories/:id/pulls/:number/files` URLs in some contexts; the client resolves them against the repository root.
- **Omitted patches.** Large or binary changes produce `patch: null`; these are recorded as coverage gaps.
- **Exact commit evidence.** Invariants and related source are fetched from the exact base or head SHA requested, never from a moving branch.
- **Nested generic types.** `ResponseEntity<List<OrderEntity>>`, `Map<String, OrderEntity>`, and `Optional<? extends OrderEntity>` resolve to the internal leaf type.
- **Overloaded methods.** Method identity uses AST node identity, not just method name, so overloaded variants do not collapse.
- **Bounded model context.** Hard caps on patch bytes, source bytes, candidate count, and context characters keep provider input predictable.
- **Bot-comment ownership and idempotency.** The marker `<!-- invariant-guardian:v2:<fingerprint> -->` and author `github-actions[bot]` are checked before any edit; unchanged bodies are not re-posted.
- **Provider failure handling.** Authentication, rate-limit, timeout, provider-unavailable, invalid-response, and internal-error cases all map to safe `assessment_incomplete` outputs.
- **Fork safety.** Fork PRs skip provider calls and comment publication.

## 5. E2E evidence

All scenarios below ran in the [`guardian-java-demo`](https://github.com/shahibag/guardian-java-demo) repository using the `v0.2.0` release and a DeepSeek provider key configured as a repository secret.

| Scenario | PR | Expected result | Actual result | Status |
| --- | --- | --- | --- | --- |
| Clean DTO boundary | [#13](https://github.com/shahibag/guardian-java-demo/pull/13) | No confirmed violations | No confirmed violations | ✅ Pass |
| Nested generic domain leak | [#14](https://github.com/shahibag/guardian-java-demo/pull/14) | Domain-leak candidate confirmed | Domain-leak candidate confirmed | ✅ Pass |
| Temporary monitoring | [#12](https://github.com/shahibag/guardian-java-demo/pull/12) | Monitoring candidate confirmed | Monitoring candidate confirmed | ✅ Pass |
| Unsupported invariant | [#9](https://github.com/shahibag/guardian-java-demo/pull/9) | Assessment incomplete | Assessment incomplete (unsupported `no-sql-injection`) | ✅ Fail-closed |

### Clean boundary (PR #13)

Bot comment excerpt:

```text
✅ No confirmed invariant violations were found in the evaluated changes.
Coverage: 1 file(s) evaluated
```

Candidate count: 0  
Coverage: complete  
[Workflow run](https://github.com/shahibag/guardian-java-demo/actions/runs/30743356481)

### Nested generic domain leak (PR #14)

Bot comment excerpt:

```text
### No internal domain or persistence leakage
- Location: src/main/java/com/example/OrderController.java:24
- Why it matters: The controller is a public boundary, and returning OrderEntity directly leaks persistence internals to API consumers.
- Evidence: Method listOrders returns OrderEntity which appears to be an internal domain/persistence type
- Suggested direction: Introduce a dedicated response DTO (e.g., OrderSummaryResponse) and map OrderEntity fields to it before returning from the controller.
```

Candidate count: 1  
Confirmed violations: 1  
Coverage: complete  
[Workflow run](https://github.com/shahibag/guardian-java-demo/actions/runs/30743362443)

### Temporary monitoring (PR #12)

Bot comment excerpt:

```text
### No temporary monitoring or retry loops masking a root-cause fix
- Location: src/main/java/com/example/OrderService.java:27
- Why it matters: The added retryUnprocessedOrders method contains a while loop that polls for unprocessed orders, changes their status to 'retrying', saves them, then sleeps 500ms.
- Evidence: Method retryUnprocessedOrders contains sleep/backoff with state-change in the same retry loop
- Suggested direction: Refactor to avoid polling. Trigger processing via an event-driven mechanism or explicit state transition.
```

Candidate count: 1  
Confirmed violations: 1  
Coverage: complete  
[Workflow run](https://github.com/shahibag/guardian-java-demo/actions/runs/30743354494)

### Unsupported invariant (PR #9)

Bot comment excerpt:

```text
⚠️ **Assessment incomplete.** This is **not** a clean review.
Coverage: 0 file(s) evaluated; context was truncated

### Notes
- Unsupported invariant ID(s) have no implemented detector: no-sql-injection.
```

This demonstrates fail-closed behavior: an unsupported ID does not return clean.

### Remediation and idempotency

Historical runs in the demo repository show a remediation update: PR code that originally exposed `OrderEntity` was corrected to return a DTO, and the bot comment updated to the clean result. The versioned marker ensures the same comment is edited and duplicates are not created.

## 6. Evaluation

The offline regression corpus lives under `tests/evaluation/`.

- **Corpus size:** 53 cases (28 domain-leak, 25 temporary-monitoring).
- **Construction:** positive cases exercise each supported pattern; negative cases cover acceptable DTOs, bounded retries, intentional scheduled jobs, records, nested generics, overloads, renamed files, large patches, and prompt-injection text.
- **Candidate precision/recall:** 100% / 100% for both invariants on the corpus.
- **Final decision precision/recall:** 100% / 100% for both invariants, using a manifest-honouring judge.
- **Incomplete tracking:** 1 domain-leak case expectedly reports incomplete due to bounded source availability.

See the full report at [`tests/evaluation/reports/evaluation.md`](tests/evaluation/reports/evaluation.md).

> Controlled regression-fixture results are not a claim of 100% accuracy on arbitrary Java repositories.

## 7. Security and reliability

- **Exact-SHA reads** prevent TOCTOU between event delivery and source retrieval.
- **No target execution** removes the risk of malicious PR code running in the CI account.
- **Bounds** on file count, patch size, source size, candidate count, and model context prevent runaway inputs.
- **URL validation** and path normalization stop traversal before local writes.
- **Sanitized errors** never include raw exceptions, response bodies, or token values in comments or logs.
- **Secret safety:** provider keys are accepted only via GitHub Actions secrets or local `.env.local`; never committed.
- **Safe mutation policy:** comments are edited only when owned by the bot and only when the rendered body changes.
- **Fail-closed behavior:** any missing required evidence returns `assessment_incomplete`.

## 8. Trade-offs and limitations

- **Narrow invariant set:** only two IDs are implemented. Arbitrary Markdown rules do not obtain detectors.
- **Java/Spring focus:** other languages and frameworks are out of scope for v0.2.
- **Controller-helper ambiguity:** public helper methods on `@RestController` / `@Controller` classes are treated as boundaries.
- **Monorepo bounds:** bounded cross-module resolution may mark some leaks incomplete rather than confirmed.
- **Provider dependency:** confirmed decisions require a working OpenAI-compatible provider.

See [`docs/known-limitations-v0.2.md`](docs/known-limitations-v0.2.md) for the complete list.

## 9. What I built

I designed and implemented Invariant Guardian v0.2 from the product boundary through release:

- Defined the repository-owned invariant format, scope model, and advisory execution policy.
- Built the `ReviewEngine` orchestration, deterministic Java AST detectors, bounded context selector, and schema-validated LLM judge contract.
- Implemented the exact-SHA GitHub reader, paginated comment publisher, bot-ownership checks, and Action outputs.
- Created the 53-case offline regression corpus, evaluation harness, and threshold reporting.
- Hardened fork safety, provider failure handling, and fail-closed behavior for unsupported/duplicate invariants and missing coverage.
- Wrote the portfolio documentation, changelog, security policy, and contributing guide.
- Curated the live demo repository and E2E scenarios.

The implementation is deliberately bounded: two invariants, one language, deterministic evidence, constrained judgment, advisory output.

## 10. Next steps

- **Controlled real-repository pilot:** run advisory mode on consenting Java/Spring repositories and label findings to validate precision before any merge-gate use.
- **Analyzer precision improvements:** tighten controller-helper boundary detection and expand measured cross-module resolution from pilot data.
- **Measured expansion:** add new invariants or languages only after pilot evidence supports the change.
