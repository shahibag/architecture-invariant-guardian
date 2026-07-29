# Invariant Guardian v0.2 — Known Limitations

This document records non-blocking analyzer and product limitations retained for v0.2 merge readiness. None of these are treated as silent false-clean paths for the advertised support matrix.

## Supported capability set

Only these invariant IDs have implemented detectors:

- `no-domain-leak`
- `no-temporary-monitoring`

Unsupported IDs, duplicate IDs, and mixed supported/unsupported sets return `assessment_incomplete`.

## Analyzer limitations deferred to v0.3

1. **Controller public helpers without route annotations**
   - Current behavior: any public method on a `@RestController` / `@Controller` / class-level `@RequestMapping` type is treated as a public boundary.
   - Risk: advisory noise when controllers expose public non-mapped helpers returning internal types.
   - Why deferred: matches a defensible reading of "public boundary"; not a false-clean path.
   - Follow-up: require method-level `@*Mapping` (or class mapping + method mapping) unless explicitly configured.

2. **Very large monorepo cross-module resolution**
   - Current behavior: Git tree scans are bounded; extra roots above the root cap are ignored; primary-root resolution remains available.
   - Risk: some cross-module domain leaks become `assessment_incomplete` rather than confirmed.
   - Why deferred: fail-closed incomplete is preferred over false clean; primary-module leaks still resolve.
   - Follow-up: smarter root discovery / paging and higher measured caps after pilot data.

3. **Broader architecture claims**
   - v0.2 does not prove arbitrary layering, package ownership, or non-Java invariants.
   - The defensible claim remains the measured two-invariant Java/Spring support matrix.

## Fixed in merge readiness

- Standard Actions `GITHUB_TOKEN` comment ownership no longer depends on successful `GET /user`.
- Nested generics such as `ResponseEntity<List<OrderEntity>>`, `Map<String, OrderEntity>`, and `Optional<? extends OrderEntity>` resolve leaf internal types.
- Overloaded methods keep their exact AST node identity instead of collapsing by method name.
- `*Aggregate` and `*PersistenceModel` remain internal without requiring JPA annotations; non-JPA `*Entity` DTOs remain acceptable.
- Failed source-root indexes no longer disable primary-root type resolution.
