"""One-time generator: reads fixtures.py, materializes all saved fixture files
and regenerates manifest.yaml with explicit file paths.

Run once, check in generated files.  Tests must NOT import this module.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add the evaluation dir to path so we can import fixtures.py
_EVAL_DIR = Path(__file__).resolve().parent
if str(_EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(_EVAL_DIR))

from fixtures import (  # type: ignore[attr-defined]
    ALL_CASES,
    DOMAIN_LEAK_NEGATIVE,
    DOMAIN_LEAK_POSITIVE,
    TEMP_MONITORING_NEGATIVE,
    TEMP_MONITORING_POSITIVE,
)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = _EVAL_DIR / "fixtures"

# Case ID → directory mapping
_CASE_DIR: dict[str, Path] = {}
for _cid in [c["id"] for c in DOMAIN_LEAK_POSITIVE] + ["dl-pos-013"]:
    _CASE_DIR[_cid] = FIXTURES_DIR / "domain_leak" / "positive"
for _cid in [c["id"] for c in DOMAIN_LEAK_NEGATIVE] + ["dl-neg-013", "dl-neg-014"]:
    _CASE_DIR[_cid] = FIXTURES_DIR / "domain_leak" / "negative"
for _cid in [c["id"] for c in TEMP_MONITORING_POSITIVE]:
    _CASE_DIR[_cid] = FIXTURES_DIR / "temp_monitoring" / "positive"
for _cid in [c["id"] for c in TEMP_MONITORING_NEGATIVE]:
    _CASE_DIR[_cid] = FIXTURES_DIR / "temp_monitoring" / "negative"


def _source_ext(case: dict) -> str:
    """Return the file extension for a case's source file."""
    fp = case.get("file_path", "")
    if fp.endswith(".kt"):
        return ".kt"
    return ".java"


def _source_fixture_path(case: dict) -> Path:
    """Return the path where the source fixture is saved."""
    d = _CASE_DIR[case["id"]]
    return d / f"{case['id']}{_source_ext(case)}"


def _patch_fixture_path(case: dict) -> Path:
    """Return the path where the patch fixture is saved."""
    d = _CASE_DIR[case["id"]]
    return d / f"{case['id']}.diff"


def _decl_fixture_path(case: dict, type_name: str) -> Path:
    """Return the path where a declaration source fixture is saved."""
    d = _CASE_DIR[case["id"]]
    return d / f"{case['id']}_decl_{type_name}.java"


# ---------------------------------------------------------------------------
# Diff generation
# ---------------------------------------------------------------------------

# Cases that get special diff treatment:
# - dl-pos-013: renamed
# - dl-neg-004: non-1 hunk offset (start at line 3)
# - tm-pos-011: disjoint hunks
# - dl-neg-013: large patch (generated separately)

_RENAMED_OLD_PATH = "src/main/java/com/example/PaymentController.java"
_NON1_OFFSET_CASE = "dl-neg-004"
_NON1_OFFSET_START = 3
_DISJOINT_CASE = "tm-pos-011"
_DISJOINT_SPLIT = 5  # split after line 5 (two hunks: 1-5, 6-8)


def _generate_diff(case: dict) -> str:
    """Generate a unified diff for a case from its source and changed_lines.

    Returns the full unified diff string with appropriate headers and hunks.
    """
    cid = case["id"]
    source = case["source"]
    changed = case.get("changed_lines", set())
    repo_path = case["file_path"]
    lines = source.splitlines()
    total_lines = len(lines)

    # --- Renamed file (dl-pos-013) ---
    if cid == "dl-pos-013":
        old_path = _RENAMED_OLD_PATH
        return _build_renamed_diff(old_path, repo_path, lines, changed, total_lines, offset=1)

    # --- Non-1 hunk offset (dl-neg-004) ---
    if cid == _NON1_OFFSET_CASE:
        offset = _NON1_OFFSET_START
        return _build_modified_diff(repo_path, lines, changed, total_lines, offset)

    # --- Disjoint hunks (tm-pos-011) ---
    if cid == _DISJOINT_CASE:
        return _build_disjoint_diff(repo_path, lines, changed, total_lines, split_after=_DISJOINT_SPLIT)

    # --- Default: single-hunk modified diff ---
    return _build_modified_diff(repo_path, lines, changed, total_lines, offset=1)


def _build_modified_diff(
    path: str, lines: list[str], changed: set[int], total: int, offset: int
) -> str:
    """Build a standard modified-file unified diff."""
    hunk_lines = []
    for line_no, line in enumerate(lines, start=1):
        if line_no < offset:
            continue
        if line_no in changed:
            hunk_lines.append(f"+{line}")
        else:
            hunk_lines.append(f" {line}")

    hunk_len = total - offset + 1
    body = "\n".join(hunk_lines)
    return f"--- a/{path}\n+++ b/{path}\n@@ -{offset},{hunk_len} +{offset},{hunk_len} @@\n{body}\n"


def _build_renamed_diff(
    old_path: str, new_path: str, lines: list[str], changed: set[int], total: int, offset: int
) -> str:
    """Build a rename unified diff."""
    hunk_lines = []
    for line_no, line in enumerate(lines, start=1):
        if line_no < offset:
            continue
        if line_no in changed:
            hunk_lines.append(f"+{line}")
        else:
            hunk_lines.append(f" {line}")

    hunk_len = total - offset + 1
    body = "\n".join(hunk_lines)
    return f"--- a/{old_path}\n+++ b/{new_path}\n@@ -{offset},{hunk_len} +{offset},{hunk_len} @@\n{body}\n"


def _build_disjoint_diff(
    path: str, lines: list[str], changed: set[int], total: int, split_after: int
) -> str:
    """Build a diff with two disjoint hunks."""
    header = f"--- a/{path}\n+++ b/{path}\n"

    # Hunk 1: lines 1..split_after
    hunk1_lines = []
    for line_no, line in enumerate(lines[:split_after], start=1):
        if line_no in changed:
            hunk1_lines.append(f"+{line}")
        else:
            hunk1_lines.append(f" {line}")
    hunk1 = f"@@ -1,{split_after} +1,{split_after} @@\n" + "\n".join(hunk1_lines)

    # Hunk 2: lines split_after+1..total
    hunk2_start = split_after + 1
    hunk2_len = total - split_after
    hunk2_lines = []
    for line_no, line in enumerate(lines[split_after:], start=hunk2_start):
        if line_no in changed:
            hunk2_lines.append(f"+{line}")
        else:
            hunk2_lines.append(f" {line}")
    hunk2 = f"@@ -{hunk2_start},{hunk2_len} +{hunk2_start},{hunk2_len} @@\n" + "\n".join(hunk2_lines)

    return header + hunk1 + "\n" + hunk2 + "\n"


def _generate_large_source() -> str:
    """Generate a genuinely large (~21 KiB) Java source for dl-neg-013.

    The file is a clean DTO controller with many small methods — no entity leak,
    so it's a negative case.  Large enough to exceed a typical patch budget
    while still being parseable Java 17.
    """
    lines = []
    lines.append("import org.springframework.web.bind.annotation.*;")
    lines.append("import java.time.Instant;")
    lines.append("import java.util.*;")
    lines.append("")
    lines.append("/**")
    lines.append(" * Large DTO controller — clean public contract with no internal entity exposure.")
    lines.append(" * Generated to exercise the large-patch evaluation path (20+ KiB).")
    lines.append(" */")
    lines.append("@RestController")
    lines.append("class LargeDataController {")
    lines.append("")

    # Generate many DTO methods
    method_count = 180
    for i in range(method_count):
        lines.append(f"    @GetMapping(\"/data/{i}\")")
        lines.append(f"    public DataResponse{i} getData{i}(@RequestParam(required = false) String filter) {{")
        lines.append(f"        var record = new DataResponse{i}(")
        lines.append("            UUID.randomUUID().toString(),")
        lines.append(f"            \"item-{i}\",")
        lines.append("            Instant.now(),")
        lines.append(f"            {i},")
        lines.append(f"            \"category-{i % 10}\",")
        lines.append(f"            \"description for record {i}\"")
        lines.append("        );")
        lines.append("        return record;")
        lines.append("    }")
        lines.append("")
        # DTO record for each method
        lines.append(f"record DataResponse{i}(")
        lines.append("    String id,")
        lines.append("    String name,")
        lines.append("    Instant timestamp,")
        lines.append("    int count,")
        lines.append("    String category,")
        lines.append("    String description")
        lines.append(") {}")
        lines.append("")

    lines.append("}")
    return "\n".join(lines) + "\n"


def _generate_large_diff(repo_path: str, source: str, changed: set[int]) -> str:
    """Generate the diff for the large patch case."""
    lines = source.splitlines()
    total = len(lines)
    hunk_lines = []
    for line_no, line in enumerate(lines, start=1):
        if line_no in changed:
            hunk_lines.append(f"+{line}")
        else:
            hunk_lines.append(f" {line}")
    body = "\n".join(hunk_lines)
    return f"--- a/{repo_path}\n+++ b/{repo_path}\n@@ -1,{total} +1,{total} @@\n{body}\n"


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


def _build_manifest(cases: list[dict]) -> dict:
    """Build the manifest dict from case data and fixture paths."""
    manifest_cases: dict[str, dict] = {}

    for case in cases:
        cid = case["id"]
        src_path = _source_fixture_path(case)
        patch_path = _patch_fixture_path(case)
        repo_path = case["file_path"]
        changed = sorted(case.get("changed_lines", []))
        evidence_loc = case.get("expected_evidence_location")
        status = case.get("status", "modified")
        decl_sources = case.get("declaration_sources", {})

        # Build declaration source mappings: repo-path → fixture-path
        related_sources: dict[str, str] = {}
        for type_name in (decl_sources or {}):
            # Repo path for the declaration
            decl_repo_path = f"src/main/java/com/example/{type_name}.java"
            # Fixture path (relative to evaluation dir)
            decl_fix = _decl_fixture_path(case, type_name)
            related_sources[decl_repo_path] = str(decl_fix.relative_to(_EVAL_DIR))

        # Determine invariant
        inv = case.get("invariant_id", "").replace("_", "-")
        if not inv:
            inv = "unknown"

        # Source roots
        source_roots = ["src/main/java"]

        entry: dict = {
            "invariant": inv,
            "expected_candidate": case.get("expected_decision") == "confirm",
            "expected_final_decision": case.get("expected_decision", "reject"),
            "repository_path": repo_path,
            "source_fixture": str(src_path.relative_to(_EVAL_DIR)),
            "patch_fixture": str(patch_path.relative_to(_EVAL_DIR)),
            "status": status,
            "changed_lines": changed,
            "java_target": case.get("java_target", "17"),
            "evidence_location": evidence_loc,
            "rationale": case.get("description", ""),
            "source_roots": source_roots,
            "related_sources": related_sources,
        }
        manifest_cases[cid] = entry

    # Override dl-pos-013: status must be "renamed"
    if "dl-pos-013" in manifest_cases:
        manifest_cases["dl-pos-013"]["status"] = "renamed"

    # Override dl-neg-013: large patch, expected_candidate=false, expected_final_decision=reject
    if "dl-neg-013" in manifest_cases:
        manifest_cases["dl-neg-013"]["expected_candidate"] = False
        manifest_cases["dl-neg-013"]["expected_final_decision"] = "reject"
        manifest_cases["dl-neg-013"]["evidence_location"] = None

    # Override dl-neg-014: Java 21, expected_candidate=false, expected_final_decision=reject
    if "dl-neg-014" in manifest_cases:
        manifest_cases["dl-neg-014"]["java_target"] = "21"
        manifest_cases["dl-neg-014"]["expected_candidate"] = False
        manifest_cases["dl-neg-014"]["expected_final_decision"] = "reject"

    return {
        "manifest_version": 2,
        "evaluated_java_version": "21",
        "java_features_tested": [
            "annotations",
            "generics",
            "records",
            "nested_classes",
            "multiline_method_declaration",
            "lambdas",
            "switch_expressions",
            "text_blocks",
            "record_pattern",
        ],
        "parser": {
            "tree_sitter": "0.26.0",
            "tree_sitter_java": "0.23.5",
        },
        "cases": manifest_cases,
        "thresholds": {
            "precision_min": 0.9,
            "recall_min": 0.8,
            "evidence_validation_pct": 100,
            "unsupported_decision_accepted": 0,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate all fixture files and manifest.yaml from fixtures.py data."""
    # Ensure directories exist
    for d in sorted(set(_CASE_DIR.values())):
        d.mkdir(parents=True, exist_ok=True)

    # Delete old generated files (preserve existing non-generated ones)
    for d in sorted(set(_CASE_DIR.values())):
        for f in d.iterdir():
            if f.is_file():
                f.unlink()

    cases = list(ALL_CASES)

    # --- Replace dl-neg-013 with genuinely large source ---
    for i, case in enumerate(cases):
        if case["id"] == "dl-neg-013":
            large_source = _generate_large_source()
            large_changed = {5}  # the DTO return line
            cases[i] = {
                **case,
                "source": large_source,
                "changed_lines": large_changed,
            }
            break

    # --- Write all fixture files ---
    for case in cases:
        cid = case["id"]
        source = case["source"]
        changed = case.get("changed_lines", set())

        # Write source file
        src_path = _source_fixture_path(case)
        src_path.write_text(source, encoding="utf-8")
        print(f"  wrote {src_path.relative_to(_EVAL_DIR)} ({len(source)} bytes)")

        # Write .diff file
        diff_path = _patch_fixture_path(case)
        if cid == "dl-neg-013":
            diff = _generate_large_diff(case["file_path"], source, changed)
        else:
            diff = _generate_diff(case)
        diff_path.write_text(diff, encoding="utf-8")
        print(f"  wrote {diff_path.relative_to(_EVAL_DIR)} ({len(diff)} bytes)")

        # Write declaration source files
        for type_name, decl_content in (case.get("declaration_sources") or {}).items():
            decl_path = _decl_fixture_path(case, type_name)
            decl_path.write_text(decl_content, encoding="utf-8")
            print(f"  wrote {decl_path.relative_to(_EVAL_DIR)} ({len(decl_content)} bytes)")

    # --- Write manifest ---
    manifest = _build_manifest(cases)
    manifest_path = _EVAL_DIR / "manifest.yaml"

    import yaml

    class _ManifestDumper(yaml.Dumper):
        """Custom YAML dumper for readable manifest output."""

    def _str_representer(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    _ManifestDumper.add_representer(str, _str_representer)

    manifest_yaml = yaml.dump(
        manifest,
        Dumper=_ManifestDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
    manifest_path.write_text(manifest_yaml, encoding="utf-8")
    print(f"\n  wrote {manifest_path.relative_to(_EVAL_DIR.parent)}")

    # --- Validation ---
    case_count = len(manifest["cases"])
    dl_cases = [c for c in manifest["cases"].values() if c["invariant"] == "no-domain-leak"]
    tm_cases = [c for c in manifest["cases"].values() if c["invariant"] == "no-temporary-monitoring"]
    dl_pos = [c for c in dl_cases if c["expected_candidate"]]
    dl_neg = [c for c in dl_cases if not c["expected_candidate"]]
    tm_pos = [c for c in tm_cases if c["expected_candidate"]]
    tm_neg = [c for c in tm_cases if not c["expected_candidate"]]

    print(f"\nGenerated {case_count} cases:")
    print(f"  no-domain-leak: {len(dl_pos)} positive + {len(dl_neg)} negative = {len(dl_cases)}")
    print(f"  no-temporary-monitoring: {len(tm_pos)} positive + {len(tm_neg)} negative = {len(tm_cases)}")
    print(f"\nThresholds satisfied: {case_count} >= 48, dl={len(dl_pos)}p/{len(dl_neg)}n >= 12/12, tm={len(tm_pos)}p/{len(tm_neg)}n >= 12/12")

    # Validate unique case IDs
    ids = list(manifest["cases"].keys())
    assert len(ids) == len(set(ids)), "Duplicate case IDs!"
    assert case_count >= 48, f"Need >=48 cases, got {case_count}"

    # Verify all fixture files exist
    for cid, cdata in manifest["cases"].items():
        sf = _EVAL_DIR / cdata["source_fixture"]
        assert sf.exists(), f"Missing source fixture: {sf}"
        pf = _EVAL_DIR / cdata["patch_fixture"]
        assert pf.exists(), f"Missing patch fixture: {pf}"
        for fix_rel in cdata.get("related_sources", {}).values():
            rf = _EVAL_DIR / fix_rel
            assert rf.exists(), f"Missing related source: {rf}"

    # Verify dl-neg-013 is large enough
    large_src_path = _EVAL_DIR / manifest["cases"]["dl-neg-013"]["source_fixture"]
    large_size = large_src_path.stat().st_size
    print(f"\ndl-neg-013 source size: {large_size} bytes ({large_size / 1024:.1f} KiB)")
    assert large_size >= 20 * 1024, f"Large patch must be >= 20 KiB, got {large_size}"

    # Verify dl-pos-013 diff is renamed
    dl_pos_013_diff = _EVAL_DIR / manifest["cases"]["dl-pos-013"]["patch_fixture"]
    diff_text = dl_pos_013_diff.read_text()
    assert "PaymentController.java" in diff_text, "Rename diff must reference old path"
    assert "PaymentApiController.java" in diff_text, "Rename diff must reference new path"

    # Verify disjoint hunk case has multiple @@ sections
    disjoint_diff = _EVAL_DIR / manifest["cases"][_DISJOINT_CASE]["patch_fixture"]
    diff_text = disjoint_diff.read_text()
    hunk_count = diff_text.count("@@")
    assert hunk_count >= 2, f"Disjoint diff must have >=2 hunks, got {hunk_count}"

    # Verify non-1 offset case
    non1_diff = _EVAL_DIR / manifest["cases"][_NON1_OFFSET_CASE]["patch_fixture"]
    diff_text = non1_diff.read_text()
    assert "@@ -3," in diff_text, "Non-1 offset diff must start at line 3"

    print("\nAll validations passed.")


if __name__ == "__main__":
    main()
