# Java Parser Compatibility Gate — v0.2

## Decision

Invariant Guardian v0.2 uses **tree-sitter** (`tree-sitter>=0.22,<1`) with the
**tree-sitter-java** grammar (`tree-sitter-java>=0.21,<1`) for Java structural
analysis.

## Compatibility Test Results

The parser was tested against all Java 17 and Java 21 syntax features required
by the v0.2 specification. All features parse without errors.

| Feature | Java Version | Passes |
| --- | --- | ---: |
| Annotations (`@RestController`, `@Entity`, `@GetMapping("/api")`) | 5+ | ✅ |
| Records (`record Point(int x, int y) {}`) | 16+ | ✅ |
| Generics (`List<OrderEntity>`, `<R> List<R> process(…)`) | 5+ | ✅ |
| Nested classes | 1+ | ✅ |
| Multiline method declarations | 1+ | ✅ |
| Lambda expressions (`x -> x > 1`) | 8+ | ✅ |
| Switch expressions (`switch(x) { case 1 -> 10; … }`) | 14+ | ✅ |
| Text blocks (`"""…"""`) | 15+ | ✅ |

## Version Pinning

- **tree-sitter**: `>=0.22,<1` — minimum 0.22 required for the stable
  `tree_sitter.Language` API and Python 3.12 wheels.
- **tree-sitter-java**: `>=0.21,<1` — tested with 0.23.5 on macOS ARM64.

Wheels are available for macOS (ARM64/x86_64) and Linux (x86_64). No
platform-specific compilation is required at install time.

## Security Boundary

- Parsing is **read-only**: tree-sitter walks the concrete syntax tree without
  executing or interpreting Java code.
- No Maven, Gradle, `javac`, annotation processors, or repository build
  scripts are invoked.
- The parser handles malformed input gracefully: invalid Java produces an
  error node in the AST but does not crash or hang.
- Source strings from pull request patches are treated as untrusted input.
  The parser uses only the `Parser.parse(bytes)` API — no file-system
  access.

## Graceful Degradation

When the AST-based detector cannot find candidates (e.g., the patch lacks
enough context for structural analysis), the Phase 1 regex-based detector
runs as a fallback. The engine never returns a falsely clean result due to
parser failure.

## Alternatives Considered

- **javac / Eclipse JDT**: Rejected — requires compiling target code, which
  violates the security boundary (spec §4, §6, §11).
- **javalang (pure-Python)**: Rejected — unmaintained, does not support
  Java 17+ syntax (records, switch expressions, text blocks).
- **ANTLR with Java grammar**: Rejected — requires grammar compilation step
  and larger dependency footprint than tree-sitter.
- **Regex-only**: Rejected per spec §8 — regex must not be the sole evidence
  for a confirmed architecture type relationship.
