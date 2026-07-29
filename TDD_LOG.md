# TDD Log — Phase 3 P1 Independent Review Fixes

**Date:** 2026-07-29
**Branch:** feat/v0.2-phase-3
**Baseline:** 465 passed

## P1#1: `_validate_next_url` exact structural endpoint equality

### RED — 7 failing tests (2026-07-29)

- `TestValidateNextUrlExactPath::test_sibling_suffix_filesevil_rejected` — startswith allows `filesevil`
- `TestValidateNextUrlExactPath::test_sibling_suffix_files_other_rejected` — startswith allows `files-other`
- `TestValidateNextUrlExactPath::test_comments_sibling_suffix_rejected` — startswith allows `comments-other`
- `TestValidateNextUrlExactPath::test_encoded_slash_path_rejected` — `%2F` not rejected
- `TestValidateNextUrlExactPath::test_params_semicolons_in_path_rejected` — `;` params not rejected
- `TestValidateNextUrlExactPath::test_sibling_suffix_url_never_requested_via_fake_transport` — wrong-resource URL is fetched
- `TestValidateNextUrlExactPath::test_encoded_slash_url_never_requested_via_fake_transport` — encoded URL is fetched

### GREEN

Replaced `parsed.path.startswith(expected_path_prefix)` with exact `parsed.path == expected_path_prefix`.
Added checks for `%2F` encoded slashes, `..`/`.` dot segments, and `;` params.

### Evidence — 8 passing + 7 new = 15 tests

```
tests/test_github_client.py::TestValidateNextUrlExactPath::test_sibling_suffix_filesevil_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_sibling_suffix_files_other_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_comments_sibling_suffix_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_encoded_slash_path_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_dot_segments_in_path_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_params_semicolons_in_path_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_other_repo_path_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_exact_path_match_with_different_query_passes PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_exact_path_match_no_query_passes PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_exact_comments_path_passes PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_wrong_resource_type_files_for_comments_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_wrong_resource_type_comments_for_files_rejected PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_sibling_suffix_url_never_requested_via_fake_transport PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_encoded_slash_url_never_requested_via_fake_transport PASSED
tests/test_github_client.py::TestValidateNextUrlExactPath::test_files_next_url_with_userinfo_rejected_before_request PASSED
```

## P1#2: `urlparse().port` ValueError → sanitized RuntimeError

### RED — 6 failing tests (2026-07-29)

- `TestUrlparseValueErrorCaught::test_validate_url_invalid_port_raises_runtime_error_not_value_error` — ValueError propagates
- `TestUrlparseValueErrorCaught::test_validate_next_url_invalid_port_raises_runtime_error` — ValueError propagates
- `TestUrlparseValueErrorCaught::test_changed_files_invalid_port_link_raises_runtime_error` — ValueError not caught
- `TestUrlparseValueErrorCaught::test_publish_invalid_port_link_raises_runtime_error` — ValueError not caught
- `TestUrlparseValueErrorCaught::test_invalid_port_url_never_reaches_transport` — ValueError propagates
- `test_action_runner.py::test_invalid_port_link_produces_assessment_incomplete_safe_outputs` — ValueError crashes ActionRunner

### GREEN

Wrapped `urlparse()` call and `.port`/`.username`/`.password` attribute accesses in `_validate_url` with try/except `ValueError` → sanitized `RuntimeError`. Same in `_validate_next_url`.

### Evidence — 6 tests

```
tests/test_github_client.py::TestUrlparseValueErrorCaught::test_validate_url_invalid_port_raises_runtime_error_not_value_error PASSED
tests/test_github_client.py::TestUrlparseValueErrorCaught::test_validate_next_url_invalid_port_raises_runtime_error PASSED
tests/test_github_client.py::TestUrlparseValueErrorCaught::test_changed_files_invalid_port_link_raises_runtime_error PASSED
tests/test_github_client.py::TestUrlparseValueErrorCaught::test_publish_invalid_port_link_raises_runtime_error PASSED
tests/test_github_client.py::TestUrlparseValueErrorCaught::test_invalid_port_url_never_reaches_transport PASSED
tests/test_action_runner.py::test_invalid_port_link_produces_assessment_incomplete_safe_outputs PASSED
```

## P1#3: Rewrite/harden Link parser

### RED — 10 failing tests (2026-07-29)

- `TestLinkParserStrictRfc8288::test_trailing_comma_rejected` — trailing comma accepted
- `TestLinkParserStrictRfc8288::test_multi_relation_rel_value_rejected` — multi-token rel accepted
- `TestLinkParserStrictRfc8288::test_unquoted_rel_whitespace_around_equals_rejected` — whitespace `=` accepted
- `TestLinkParserStrictRfc8288::test_unquoted_rel_with_trailing_whitespace_around_equals_rejected` — space before `=` accepted
- `TestLinkParserStrictRfc8288::test_unquoted_rel_with_space_after_equals_rejected` — space after `=` accepted
- `TestLinkParserStrictRfc8288::test_empty_element_between_commas_rejected` — empty elements skipped
- `TestLinkParserStrictRfc8288::test_changed_files_trailing_comma_link_raises` — clean result leaked
- `TestLinkParserStrictRfc8288::test_changed_files_multi_relation_rel_link_raises` — clean result leaked
- `TestLinkParserStrictRfc8288::test_changed_files_rel_whitespace_link_raises` — clean result leaked
- `TestLinkParserStrictRfc8288::test_publish_trailing_comma_link_no_mutation` — mutation allowed

### GREEN

Tightened `_LINK_VALUE_RE` regex to not allow whitespace around `=`. Rewrote `_parse_link_header` to reject empty elements, multi-token quoted rel values, and strengthened param validation.

### Evidence — 19 tests

```
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_trailing_comma_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_multi_relation_rel_value_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_unquoted_rel_whitespace_around_equals_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_quoted_rel_whitespace_around_equals_still_works PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_normal_unquoted_rel_still_works PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_unquoted_rel_with_trailing_whitespace_around_equals_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_unquoted_rel_with_space_after_equals_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_valid_prev_last_only_returns_empty PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_valid_prev_only_returns_empty PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_valid_last_only_returns_empty PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_empty_element_between_commas_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_leading_comma_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_completely_unknown_param_still_parses PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_param_with_no_value_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_duplicate_next_across_entries_rejected PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_changed_files_trailing_comma_link_raises PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_changed_files_multi_relation_rel_link_raises PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_changed_files_rel_whitespace_link_raises PASSED
tests/test_github_client.py::TestLinkParserStrictRfc8288::test_publish_trailing_comma_link_no_mutation PASSED
```

## Full Suite Result

**506 passed** (465 baseline + 41 new P1 regression tests)
- Ruff: PASS
- mypy: PASS
- git diff --check: PASS
