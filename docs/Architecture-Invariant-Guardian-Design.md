# Architecture Invariant Guardian — Planning Design Document

> **Implementation status:** This is the original planning document. The agreed source of truth for the build is [Implementation-Ready MVP Specification](implementation-ready-mvp.md), which narrows the project to the two validated invariants, Python Docker Action runtime, OpenAI-first provider boundary, Markdown-only policy files, and the required security policy.

This document combines the four design artifacts produced during the planning phase.

---


# Detailed Interface Contracts

This document defines the contracts between the core components of the MVP GitHub Action.

---

## 1. Context Collector

**Responsibility**  
Gather the minimal, high-signal context required for evaluation while respecting the token budget.

### Input
- `pr_number: number`
- `repo: { owner: string, name: string }`
- `github_token: string`

### Output
```ts
interface EvaluationContext {
  diff: string;                       // full unified diff of the PR
  changedFiles: ChangedFile[];
  relatedFiles: RelatedFile[];        // only populated when deterministic checks request them
  tokenEstimate: number;              // rough estimate of tokens that will be sent to the LLM
  truncated: boolean;                 // true if we had to truncate due to budget
}

interface ChangedFile {
  path: string;                       // e.g. "src/main/java/com/example/OrderService.java"
  language: "java";
  patch: string;                      // the hunk for this file
  surroundingContext: string;         // class + modified methods + public signatures
  fullContent?: string;               // only if the file is small
}

interface RelatedFile {
  path: string;
  reason: string;                     // why it was pulled in
  content: string;
}
```

### Behavioural Rules
- Always include the full PR diff.
- For every changed `.java` file, extract the enclosing class and the methods that were modified.
- Never exceed the configured token budget (default ~10k tokens of code).
- If truncation is required, prefer keeping the most recently changed files and the files that deterministic checks later flag.
- Must never throw on missing files or binary files; skip them with a warning in logs.

---

## 2. Invariant Loader

**Responsibility**  
Load and parse the human-owned architectural invariants from the repository.

### Input
- `repo_root: string` (or GitHub API client)
- `invariant_paths: string[]` (default: `[".guardian/invariants/", "ARCHITECTURE.md"]`)

### Output
```ts
interface Invariant {
  id: string;                         // stable identifier, e.g. "no-temporary-monitoring"
  title: string;
  description: string;                // the full rule text
  severity: "error" | "warning";
  examples?: string[];                // optional concrete examples of violations
  tags?: string[];                    // e.g. ["resilience", "boundaries"]
}

interface LoadResult {
  invariants: Invariant[];
  source: string;                     // which file(s) were used
  warnings: string[];                 // e.g. "no invariant files found"
}
```

### Behavioural Rules
- If no invariant files exist → return empty list + a clear warning (the Action will post an informational comment and exit).
- Support both a directory of individual Markdown/YAML files and a single `ARCHITECTURE.md` with clearly delimited sections.
- IDs must be stable (derived from filename or explicit front-matter).

---

## 3. Deterministic Checker

**Responsibility**  
Produce fast, high-precision signals that reduce reliance on the LLM and catch obvious cases of the three MVP invariants.

### Input
```ts
interface DeterministicInput {
  context: EvaluationContext;
  invariants: Invariant[];
}
```

### Output
```ts
interface DeterministicFinding {
  invariantId: string;
  file: string;
  startLine: number;
  endLine: number;
  evidence: string;                   // short human-readable evidence
  confidence: "high" | "medium";
  pattern: string;                    // which rule matched
}

interface DeterministicResult {
  findings: DeterministicFinding[];
  requestedRelatedFiles: string[];    // paths the Context Collector should try to fetch
}
```

### Behavioural Rules (MVP)
- Must be pure and fast (no network, no LLM).
- Focus only on the three agreed invariants.
- Prefer high precision over high recall. False positives here are expensive.
- Can request additional related files; the Context Collector will attempt to fulfil the request within budget.

---

## 4. LLM Judge

**Responsibility**  
Perform higher-level architectural judgment and produce the structured data needed for the final comment.

### Input
```ts
interface JudgeInput {
  invariants: Invariant[];
  context: EvaluationContext;
  deterministicFindings: DeterministicFinding[];
  model: string;                      // configurable
  maxTokens: number;
}
```

### Output (strict schema)
```ts
interface Violation {
  invariantId: string;
  title: string;
  file: string;
  startLine: number;
  endLine?: number;
  whyItMatters: string;               // 1–3 sentences
  evidence: string[];                 // bullet points citing the code
  suggestedDirection: string;         // constructive alternative
  confidence: "high" | "medium" | "low";
}

interface JudgeResult {
  violations: Violation[];
  rawModelResponse?: string;          // for debugging
  tokenUsage: { prompt: number; completion: number };
}
```

### Behavioural Rules
- Must use structured output (JSON mode or tool calling).
- Must cite concrete evidence from the provided context.
- Should treat deterministic findings as strong prior signals but can override them with justification.
- Must respect the token budget. If the context is too large, the Context Collector is responsible for truncation; the Judge should not attempt further truncation.
- On model failure or malformed response → return empty violations list and log the error (do not crash the Action).

---

## 5. Comment Renderer & Poster

**Responsibility**  
Turn structured violations into the exact human-facing PR comment and post it via the GitHub API.

### Input
```ts
interface RenderInput {
  violations: Violation[];
  invariants: Invariant[];
  prNumber: number;
  repo: { owner: string; name: string };
  githubToken: string;
}
```

### Output
```ts
interface PostResult {
  commentIds: number[];
  posted: boolean;
  skippedReason?: string;             // e.g. "no violations"
}
```

### Behavioural Rules
- Use the exact comment template agreed in the design:
  - Invariant name
  - Location
  - Why it matters
  - Evidence
  - Suggested direction
  - Clear human action (“Reply with `acknowledge` …”)
- Prefer one well-structured comment that groups multiple violations rather than spamming many comments.
- Be idempotent where practical (avoid duplicate comments on every `synchronize` event if the violations have not changed).
- Never fail the GitHub check run just because violations were found.

---

## 6. Acknowledgment Detector (lightweight, optional in first slice)

**Responsibility**  
Detect whether a human has already acknowledged a previous comment so future runs can note it.

### Input
- PR comments (via GitHub API)

### Output
```ts
interface Acknowledgment {
  violationKey: string;               // derived from invariantId + file + line
  acknowledgedBy: string;
  acknowledgedAt: string;
  commentId: number;
}
```

### Behavioural Rules (MVP)
- Simple keyword match (`acknowledge`, `accepted risk`, `I accept`, etc.) from non-bot users.
- Can be expanded later into a persistent store.

---

## Cross-Cutting Contracts

- All components must be pure where possible and side-effect free except for the final Poster and logging.
- Every component logs structured information (component name, duration, key counts).
- Configuration (token budget, model name, invariant paths, etc.) is injected from the Action inputs / environment.
- Failures in any component except the Poster should be caught, logged, and result in a soft informational comment rather than a hard Action failure.


---


# Proposed Repository / Folder Structure

This document describes the recommended layout for the Guardian project itself and for a target repository that uses the Guardian.

---

## 1. Guardian Project Structure (the tool we are building)

```
architecture-invariant-guardian/
├── .github/
│   └── workflows/
│       └── self-test.yml                 # optional: test the Action on itself
├── action.yml                            # GitHub Action entrypoint definition
├── package.json                          # or requirements.txt / pyproject.toml
├── src/
│   ├── index.ts                          # Action entrypoint
│   ├── context-collector.ts
│   ├── invariant-loader.ts
│   ├── deterministic-checker.ts
│   ├── llm-judge.ts
│   ├── comment-renderer.ts
│   ├── acknowledgment-detector.ts        # optional in first slices
│   ├── types.ts                          # shared interfaces
│   └── utils/
│       ├── github.ts
│       ├── tokens.ts
│       └── logging.ts
├── invariants/                           # example invariants used for demos & tests
│   ├── no-temporary-monitoring.md
│   ├── no-domain-leak.md
│   └── explicit-cross-cutting-ownership.md
├── test/
│   ├── fixtures/
│   │   ├── clean-pr/
│   │   ├── monitoring-loop-pr/
│   │   ├── domain-leak-pr/
│   │   └── cross-cutting-pr/
│   ├── deterministic-checker.test.ts
│   ├── invariant-loader.test.ts
│   └── ...
├── demos/
│   └── java-sample-service/              # small Java repo used for the public demo
├── docs/
│   ├── design/
│   │   ├── 01-interface-contracts.md
│   │   ├── 02-repository-structure.md
│   │   ├── 03-invariant-file-format.md
│   │   └── 04-implementation-slices.md
│   └── usage.md
├── README.md
└── LICENSE
```

### Notes
- Keep the Action self-contained. Prefer zero external services for the MVP.
- The `invariants/` folder inside the Guardian repo is only for examples and tests. Real target repositories will own their own invariants.
- The `demos/java-sample-service` is the public demo repository (or a submodule / separate repo) that shows the end-to-end flow.

---

## 2. Target Repository Structure (a Java project that uses the Guardian)

```
my-java-service/
├── .github/
│   └── workflows/
│       └── guardian.yml                  # calls the Guardian Action
├── .guardian/
│   └── invariants/
│       ├── no-temporary-monitoring.md
│       ├── no-domain-leak.md
│       └── explicit-cross-cutting-ownership.md
├── src/
│   └── main/java/...
├── ARCHITECTURE.md                       # optional higher-level doc (can also contain invariants)
└── ...
```

### Recommended Convention
- Primary location for invariants: `.guardian/invariants/*.md` (or `.yml`)
- Fallback / additional location: top-level `ARCHITECTURE.md` with clearly delimited sections
- The Action should look in both places (configurable via Action inputs)

---

## 3. GitHub Action Workflow Example (for a target repo)

```yaml
# .github/workflows/guardian.yml
name: Architecture Invariant Guardian

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  guardian:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      issues: write
    steps:
      - uses: actions/checkout@v4
      - name: Run Architecture Invariant Guardian
        uses: your-org/architecture-invariant-guardian@v1   # or local path during development
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          llm-api-key: ${{ secrets.LLM_API_KEY }}
          model: "claude-sonnet-4-20250514"               # configurable
          max-code-tokens: 10000
          invariant-paths: ".guardian/invariants/,ARCHITECTURE.md"
```

---

## 4. Design Principles Reflected in the Structure

- Invariants live in the target repository and are versioned with the code (human ownership).
- The Guardian Action itself is a pure consumer of those files.
- Demo and test fixtures are first-class so detection quality can be measured.
- Documentation of the design decisions lives inside the repo for future maintainers (and for the portfolio story).


---


# Exact Invariant File Format

Invariants are human-owned, versioned with the codebase, and deliberately simple.

---

## 1. Recommended Location

Primary:
```
.guardian/invariants/
├── no-temporary-monitoring.md
├── no-domain-leak.md
└── explicit-cross-cutting-ownership.md
```

Optional additional source:
```
ARCHITECTURE.md          # can also contain invariants in clearly marked sections
```

---

## 2. Markdown Format (preferred for MVP)

Each file is a single invariant.

```markdown
---
id: no-temporary-monitoring
title: No temporary monitoring / retry loops as a substitute for root-cause fixes
severity: error
tags: [resilience, design-debt]
---

## Rule

Prefer fixing the underlying condition over introducing a background monitor, scheduler, polling loop, or retry mechanism that papers over the problem.

## Why this matters

Coding agents frequently respond to flaky calls, missing events, or incomplete state transitions by adding a `@Scheduled` method, a retry loop with `Thread.sleep`, or a watcher thread. The resulting code passes tests but hides the real design problem, accumulates load, and makes the system harder to reason about.

## Examples of violations

- Adding a `@Scheduled` method that repeatedly checks for unprocessed orders instead of emitting or reacting to a domain event.
- Introducing a recursive retry with sleep inside business logic when a downstream service is unavailable.
- Creating a background thread that polls a database table for a condition that should be event-driven.

## Examples of acceptable patterns

- A genuine scheduled job that is the *source* of truth for a periodic business process (e.g. daily reconciliation).
- Explicit retry policies with clear ownership (e.g. inside a dedicated resilience module) that are not papering over a missing domain event.
```

### Front-matter fields

| Field       | Required | Description                                      |
|-------------|----------|--------------------------------------------------|
| `id`        | yes      | Stable machine-readable identifier               |
| `title`     | yes      | Short human title                                |
| `severity`  | no       | `error` (default) or `warning`                   |
| `tags`      | no       | Free-form labels                                 |

---

## 3. Alternative: YAML Format

Also supported for teams that prefer pure data.

```yaml
id: no-domain-leak
title: No leaking of internal domain objects across boundaries
severity: error
tags:
  - boundaries
  - encapsulation
description: |
  Public APIs and inter-module contracts must not expose internal domain entities,
  persistence models, or implementation-specific types.
examples:
  - Returning a JPA `@Entity` directly from a REST controller.
  - Passing an internal `OrderAggregate` into another bounded context.
acceptable:
  - Returning a dedicated response DTO or a public domain event.
```

---

## 4. The Three MVP Invariants (exact content)

### 4.1 `no-temporary-monitoring.md`

```markdown
---
id: no-temporary-monitoring
title: No temporary monitoring / retry loops as a substitute for root-cause fixes
severity: error
tags: [resilience, design-debt]
---

## Rule

Prefer fixing the underlying condition over introducing a background monitor, scheduler, polling loop, or retry mechanism that papers over the problem.

## Why this matters

Agents commonly respond to incomplete state or flaky dependencies by adding temporary monitoring. This creates hidden load, race conditions, and design debt that is expensive to remove later.

## Examples of violations

- New `@Scheduled` or `ScheduledExecutorService` introduced in the same change that also modifies the business logic it is watching.
- Retry loops with sleep or busy-wait that mask a missing domain event or incorrect state transition.
```

### 4.2 `no-domain-leak.md`

```markdown
---
id: no-domain-leak
title: No leaking of internal domain objects across module or service boundaries
severity: error
tags: [boundaries, encapsulation]
---

## Rule

Public APIs and inter-module contracts must not expose internal domain entities, persistence models, or implementation-specific types.

## Why this matters

Exposing internal types couples callers to implementation details and makes future refactoring expensive. Agents do this constantly because it is the shortest path to making tests pass.

## Examples of violations

- A controller or public facade returning a JPA entity or an internal aggregate.
- Passing a persistence model into another bounded context or module.
```

### 4.3 `explicit-cross-cutting-ownership.md`

```markdown
---
id: explicit-cross-cutting-ownership
title: Explicit ownership of new cross-cutting concerns
severity: warning
tags: [ownership, modularity]
---

## Rule

Any new logging, metrics, caching, resilience, or similar cross-cutting behaviour must declare which existing module or component owns it, or must create a clearly named new owner. No anonymous utility dumps.

## Why this matters

Unowned cross-cutting code accumulates silently and becomes nobody’s responsibility. Agents frequently sprinkle such behaviour into random places.
```

---

## 5. Parsing Rules for the Loader

1. Prefer files under `.guardian/invariants/`.
2. Also scan `ARCHITECTURE.md` for sections that begin with a recognised heading or front-matter block.
3. Each invariant must have a stable `id`.
4. Missing or malformed files produce warnings, never hard failures.
5. The Loader returns a clean list of `Invariant` objects (see interface contracts).


---


# First Implementation Slices

Goal: reach a credible, demoable MVP in roughly 1–2 weeks of focused work by a single engineer.

Each slice ends with something observable and testable.

---

## Day 1–2 — Foundation & Invariant Loading

**Objective**  
Have a working GitHub Action skeleton that can read invariants and post a simple comment.

### Tasks
- Create the repository with the structure defined in `02-repository-structure.md`
- Write `action.yml` with the necessary inputs (`github-token`, `llm-api-key`, `model`, `max-code-tokens`, `invariant-paths`)
- Implement **Invariant Loader**
  - Support Markdown with front-matter (primary)
  - Support simple YAML
  - Return structured `Invariant[]`
- Implement a minimal **Comment Renderer & Poster** that can post a hard-coded test comment on a PR
- Wire a basic GitHub Action workflow that runs on `pull_request`
- Add the three MVP invariant files under `.guardian/invariants/` (and also under the Guardian’s own `invariants/` for examples)
- Write unit tests for the loader

### Done when
- Opening a PR on a test repo causes the Action to run and post a comment (even if the comment is still placeholder text)
- Invariants are correctly loaded from the repo

---

## Day 3–4 — Context Collection & Deterministic Checks

**Objective**  
Be able to gather the right code context and produce high-precision deterministic findings for the three invariants.

### Tasks
- Implement **Context Collector**
  - Fetch PR diff via GitHub API
  - Extract changed `.java` files + surrounding class/method context
  - Respect token budget (simple character/token estimate is fine)
- Implement **Deterministic Checker** focused on the three MVP rules:
  - Detection of new `@Scheduled` / polling / retry patterns
  - Detection of internal domain/persistence types appearing in public signatures
  - Basic signals for new cross-cutting calls without clear ownership
- Pass deterministic findings into a temporary log or placeholder Judge
- Add fixtures under `test/fixtures/` for:
  - Clean PR
  - Monitoring-loop violation
  - Domain-leak violation
- Unit tests for both Context Collector and Deterministic Checker

### Done when
- On a fixture PR that contains a clear monitoring loop, the deterministic checker emits a high-confidence finding with correct file + line
- Token budget is respected on larger diffs

---

## Day 5–6 — LLM Judge & Real Comments

**Objective**  
Replace the placeholder with a real hybrid evaluation and the final human-facing comment format.

### Tasks
- Implement **LLM Judge**
  - Strict structured JSON output schema (see interface contracts)
  - Prompt that includes invariants + context + deterministic findings
  - Configurable model + hard token/cost guardrail
- Connect Judge → Comment Renderer
- Implement the exact comment template agreed in the design
- Handle the “no invariants found” and “no violations found” cases cleanly
- Add basic retry / error handling so a model failure does not crash the Action
- End-to-end test on the fixture PRs

### Done when
- A PR containing a deliberate domain-leak produces a well-structured comment that names the invariant, shows evidence, and suggests a direction
- False-positive rate on clean fixtures is low
- The Action never fails the GitHub check just because violations were found

---

## Day 7–8 — Demo Repository, Polish & Measurement

**Objective**  
Create the public (or shareable) demo and measure against the success criteria.

### Tasks
- Create or finalise `demos/java-sample-service` (small Spring Boot or plain Java service)
- Seed a few realistic agent-style PRs (or generate them) that violate the three invariants
- Run the Guardian against them and capture screenshots / comment links
- Implement lightweight acknowledgment detection (keyword match) if time permits
- Add clear logging and a short usage section in the README
- Measure:
  - Recall on the curated violation set
  - False positives on clean PRs
  - Time for a human to decide on a comment
- Write a short “How it works” section and the portfolio story outline

### Done when
- There is a public or easily shareable repository demonstrating:
  Agent introduces violation → Guardian posts structured comment → human can acknowledge
- The four success criteria defined in the grill are met or clearly documented

---

## After MVP (explicitly later)

- Local CLI
- Hard status-check / required review mode
- More invariants (microservices, event-driven, etc.)
- Learning from acknowledgments
- TypeScript / Python support
- Richer static analysis (real Java AST, call graphs)
- Dashboard / historical tracking

---

## Working Principles for All Slices

- Prefer working end-to-end vertical slices over perfect horizontal layers.
- Keep the deterministic checks high-precision; let the LLM handle nuance.
- Every slice should leave the Action in a runnable state.
- Capture at least one concrete before/after example for the portfolio story as soon as the comment format works.


---
