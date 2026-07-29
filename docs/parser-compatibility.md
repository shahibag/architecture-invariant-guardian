# Java Parser Compatibility Gate — v0.2

## Decision

Invariant Guardian v0.2 uses **tree-sitter** with the
**tree-sitter-java** grammar for Java structural analysis.

## Exact Dependency Matrix

| Component | Version | Notes |
| --- | --- | --- |
| tree-sitter | 0.26.0 | `==0.26.0` in pyproject.toml |
| tree-sitter-java | 0.23.5 | `==0.23.5` in pyproject.toml |
| Python | 3.12 | `>=3.12` in pyproject.toml |
| Platform | macOS ARM64 | Linux x86_64 wheels available |

**Parser-pair reproducibility:** The tree-sitter and tree-sitter-java versions are
pinned in `constraints.txt` and applied by `pip install -c constraints.txt .` and
`docker build --no-cache .` (the Dockerfile copies and applies constraints.txt).
Other build and runtime dependencies are ranged in `pyproject.toml` — the
constraints file guarantees parser-version reproducibility, not a full
dependency lock.

## Fixture Java Version Metadata

Evaluation fixtures target Java 17 as the primary version.  One fixture
(dl-neg-014) uses genuine Java 21 record-pattern syntax (`instanceof Point(var x, var y)`).
Records and text blocks are finalized well before Java 17 (records: Java 16 GA;
text blocks: Java 15 GA) and are tracked under the Java 17 target.

| Fixture ID | Java Target | Syntax Features |
| --- | --- | --- |
| dl-neg-014 | 21 | record pattern in instanceof (Java 21) |
| All other fixtures | 17 | annotations, generics, records, lambdas, text blocks, etc. |

Per-case `java_target` metadata is checked against the authoritative
`tests/evaluation/manifest.yaml` during evaluation — the manifest and fixture
module agree, and `test_manifest_java_targets_consistent` enforces this.

## Compatibility Test Results

The parser was tested against all Java 17 and Java 21 syntax features required
by the v0.2 specification. All features parse without errors.

| Feature | Intro'd | Passes |
| --- | --- | ---: |
| Annotations (`@RestController`, `@Entity`, `@GetMapping("/api")`) | 5 | ✅ |
| Records (`record Point(int x, int y) {}`) | 14(preview)/16 | ✅ |
| Generics (`List<OrderEntity>`, `<R> List<R> process(…)`) | 5 | ✅ |
| Nested classes | 1 | ✅ |
| Multiline method declarations | 1 | ✅ |
| Lambda expressions (`x -> x > 1`) | 8 | ✅ |
| Switch expressions (`switch(x) { case 1 -> 10; … }`) | 14 | ✅ |
| Text blocks (`"""…"""`) | 13(preview)/15 | ✅ |
| Record patterns (`o instanceof Point(var x, var y)`) | 19(preview)/21 | ✅ |

## Security Boundary

- Parsing is **read-only**: tree-sitter walks the concrete syntax tree without
  executing or interpreting Java code.
- No Maven, Gradle, `javac`, annotation processors, or repository build
  scripts are invoked.
- The parser rejects malformed input: invalid Java produces an ERROR node
  in the AST, causing `parse_java_source` to raise `ValueError`.  Partial
  recovery never produces confirmable candidates.
- Source strings from pull request patches are treated as untrusted input.
  The parser uses only the `Parser.parse(bytes)` API — no file-system
  access.

## Graceful Degradation

When production AST analysis cannot produce complete structural evidence
(parser error, incomplete source, or unavailable related declaration), the
assessment records a coverage gap and returns `assessment_incomplete`.
Production `ReviewEngine` does not fall back to regex, so regex-only text can
never become a confirmable structural relationship or monitoring finding. The
legacy `assess_diff` API retains its Phase 1 regex behavior for compatibility.

## Alternatives Considered

- **javac / Eclipse JDT**: Rejected — requires compiling target code, which
  violates the security boundary (spec §4, §6, §11).
- **javalang (pure-Python)**: Rejected — unmaintained, does not support
  Java 17+ syntax (records, switch expressions, text blocks).
- **ANTLR with Java grammar**: Rejected — requires grammar compilation step
  and larger dependency footprint than tree-sitter.
- **Regex-only**: Rejected per spec §8 — regex must not be the sole evidence
  for a confirmed architecture type relationship.
