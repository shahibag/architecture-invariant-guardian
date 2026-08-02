# Changelog

All notable changes to Invariant Guardian are documented in this file.

## [0.2.0] - 2026-08-02

### Added

- Repository-owned Markdown invariant loader with explicit scope (`languages`, `include_paths`) and execution policy.
- Deterministic Java AST candidate detection using Tree-sitter for:
  - `no-domain-leak` — persistence entities exposed through public Spring boundaries.
  - `no-temporary-monitoring` — scheduled/retry/polling workarounds masking root-cause fixes.
- Exact-SHA GitHub Contents reader: invariant files and related Java source are fetched from the precise base or head commit, never from a moving branch.
- Scope and coverage accounting: changed-file caps, patch-size caps, source-size caps, candidate caps, and model-context caps; every omission is recorded as a coverage gap.
- Bounded evidence package sent to a constrained LLM judge: only the invariant text, candidate record, changed hunks, and bounded declaration context.
- OpenAI-compatible judge adapter with explicit JSON output schema, response validation, timeout, and safe error classification.
- Fail-closed `assessment_incomplete` status for unsupported/duplicate invariant IDs, missing patches, oversized context, provider failures, and schema violations.
- Safe, idempotent PR comments owned by `github-actions[bot]`, with a versioned marker and no update when the rendered body is unchanged.
- Action outputs: `assessment-status`, `confirmed-count`, `candidate-count`, and `coverage-complete`.
- 53-case offline regression corpus under `tests/evaluation/` with manifest-honouring judge and published precision/recall report.
- Docker packaging and GitHub Actions `uses: ./` contract test.
- Fork-pull-request safety: no provider calls and no comment publication for forks.

### Changed

- Replaced whole-diff LLM judgment with per-candidate bounded evidence and deterministic candidate detection.
- Migrated Java analysis from naming regexes to Tree-sitter AST fact extraction for return types, parameters, generics, annotations, and enclosing declarations.
- Upgraded GitHub client to paginate changed files and comments, handle renamed files, and decode newline-wrapped Base64 contents.
- README rewritten as portfolio landing page with problem statement, safety properties, evidence, and quick-start workflow.

### Fixed

- Newline-wrapped Base64 returned by the GitHub Contents API is now decoded correctly.
- GitHub repositories-id pagination URL variant is accepted.
- Omitted patches are recorded as coverage gaps instead of being silently skipped.
- Nested generic leaves (`ResponseEntity<List<OrderEntity>>`, `Map<String, OrderEntity>`, `Optional<? extends OrderEntity>`) resolve correctly.
- Overloaded methods keep their exact AST node identity instead of collapsing by method name.
- `*Aggregate` and `*PersistenceModel` naming suffixes are treated as internal without requiring JPA annotations.
- Standard `GITHUB_TOKEN` comment ownership no longer depends on a successful `GET /user` call.
- Provider failures return `assessment_incomplete` rather than crashing or reporting a false clean result.

### Security

- Provider API keys are accepted only through GitHub Actions secrets or local `.env.local`; never logged, rendered, or never committed.
- Target-repository Java code is parsed, never compiled or executed.
- Repository paths are validated before local writes.
- HTTP response sizes are capped before decoding.
- Prompt-injection text in source comments, string literals, and invariant prose cannot alter the judge contract.

### Known limitations

- Only `no-domain-leak` and `no-temporary-monitoring` have implemented detectors. Unsupported or duplicate IDs return `assessment_incomplete`.
- Public helper methods on `@RestController` / `@Controller` classes are treated as public boundaries even without method-level `@*Mapping` annotations.
- Cross-module type resolution uses bounded Git tree scans; very large monorepos may mark some cross-module leaks incomplete.
- Nested generic leaves, overload identity, and `Aggregate`/`PersistenceModel` naming without JPA are supported for the advertised patterns only.
- Live provider judgment is optional in CI; provider failures always yield `assessment_incomplete`.

See [`docs/known-limitations-v0.2.md`](docs/known-limitations-v0.2.md) for the full v0.2 limitation record.
