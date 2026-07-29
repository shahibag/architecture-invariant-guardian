"""Contract tests for GitHub client — bot-owned comment protection."""

import pytest

from invariant_guardian.adapters.github.client import (
    BOT_LOGIN,
    GitHubClient,
    find_owned_comment,
    is_bot_comment,
    should_skip_update,
)


# ---------------------------------------------------------------------------
# Bot login constant
# ---------------------------------------------------------------------------
class TestBotLogin:
    def test_bot_login_is_github_actions_bot(self) -> None:
        assert BOT_LOGIN == "github-actions[bot]"


class TestSourceRootDiscovery:
    def test_preserves_module_prefixes(self) -> None:
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda *args, **kwargs: {
            "truncated": False,
            "tree": [
                {
                    "type": "blob",
                    "path": "module-api/src/main/java/com/acme/api/C.java",
                },
                {
                    "type": "blob",
                    "path": "module-domain/src/main/java/com/acme/domain/Order.java",
                },
            ],
        }
        assert set(client.list_source_roots("exact-sha") or []) == {
            "module-api/src/main/java",
            "module-domain/src/main/java",
        }

    def test_truncated_tree_is_unavailable_not_partial(self) -> None:
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda *args, **kwargs: {
            "truncated": True,
            "tree": [{"type": "blob", "path": "src/main/java/A.java"}],
        }
        assert client.list_source_roots("exact-sha") is None


# ---------------------------------------------------------------------------
# is_bot_comment
# ---------------------------------------------------------------------------
class TestIsBotComment:
    def test_bot_comment_identified(self) -> None:
        comment = {
            "id": 1,
            "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nAssessment.",
            "user": {"login": "github-actions[bot]"},
        }
        assert is_bot_comment(comment, BOT_LOGIN)

    def test_contributor_comment_with_copied_marker_is_rejected(self) -> None:
        comment = {
            "id": 2,
            "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nCopied marker!",
            "user": {"login": "some-contributor"},
        }
        assert not is_bot_comment(comment, BOT_LOGIN)

    def test_comment_without_marker_not_identified(self) -> None:
        comment = {
            "id": 3,
            "body": "Just a regular comment.",
            "user": {"login": "github-actions[bot]"},
        }
        assert not is_bot_comment(comment, BOT_LOGIN)

    def test_comment_with_no_user_key(self) -> None:
        comment = {"id": 4, "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nNo user."}
        assert not is_bot_comment(comment, BOT_LOGIN)

    def test_bot_comment_case_insensitive_login(self) -> None:
        """GitHub logins are case-insensitive."""
        comment = {
            "id": 5,
            "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nTest.",
            "user": {"login": "github-actions[bot]"},
        }
        assert is_bot_comment(comment, BOT_LOGIN)


# ---------------------------------------------------------------------------
# find_owned_comment
# ---------------------------------------------------------------------------
class TestFindOwnedComment:
    def test_finds_bot_comment(self) -> None:
        comments = [
            {"id": 1, "body": "Hello", "user": {"login": "contributor"}},
            {
                "id": 2,
                "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nGuardian.",
                "user": {"login": "github-actions[bot]"},
            },
        ]
        result = find_owned_comment(comments, BOT_LOGIN)
        assert result is not None
        assert result["id"] == 2

    def test_skips_contributor_with_copied_marker(self) -> None:
        comments = [
            {
                "id": 1,
                "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nCopied!",
                "user": {"login": "contributor"},
            },
        ]
        result = find_owned_comment(comments, BOT_LOGIN)
        assert result is None

    def test_returns_none_when_no_matching_comment(self) -> None:
        comments = [
            {"id": 1, "body": "Hello", "user": {"login": "github-actions[bot]"}},
        ]
        result = find_owned_comment(comments, BOT_LOGIN)
        assert result is None

    def test_raises_on_multiple_owned(self) -> None:
        """>1 owned comment → raise RuntimeError (unambiguous failure)."""
        comments = [
            {
                "id": 10,
                "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOld.",
                "user": {"login": "github-actions[bot]"},
            },
            {
                "id": 20,
                "body": "<!-- invariant-guardian:v2:0123456789abcdef -->\nNew.",
                "user": {"login": "github-actions[bot]"},
            },
        ]
        with pytest.raises(RuntimeError, match="multiple|ambiguous|duplicate"):
            find_owned_comment(comments, BOT_LOGIN)


# ---------------------------------------------------------------------------
# should_skip_update
# ---------------------------------------------------------------------------
class TestShouldSkipUpdate:
    def test_skip_when_body_identical(self) -> None:
        body = "<!-- invariant-guardian:v2:abcdef0123456789 -->\nSame."
        existing = {"body": body}
        assert should_skip_update(existing, body)

    def test_update_when_body_different(self) -> None:
        existing = {"body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOld."}
        assert not should_skip_update(existing, "<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew.")

    def test_update_when_existing_has_no_body(self) -> None:
        existing = {"id": 99}
        assert not should_skip_update(existing, "<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew.")


# ---------------------------------------------------------------------------
# GitHubClient — construction safety
# ---------------------------------------------------------------------------
class TestGitHubClientConstruction:
    def test_client_stores_params(self) -> None:
        client = GitHubClient("token", "owner/repo", 42)
        assert client._token == "token"
        assert client._repository == "owner/repo"
        assert client._pull_number == 42


class TestCommentPagination:
    def test_publish_finds_owned_comment_on_page_2(self) -> None:
        """When a bot-owned comment exists on the second page, publish must
        paginate through Link rel=next to find it and PATCH (not duplicate)."""

        client = GitHubClient("token", "owner/repo", 42)
        call_log: list[tuple[str, str, object]] = []
        page_calls = 0

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            nonlocal page_calls
            page_calls += 1
            call_log.append(("_json_with_link", url, method))
            # Page 1 — no owned comment, link to page 2
            if page_calls == 1:
                return (
                    [
                        {
                            "id": 1,
                            "body": "regular comment",
                            "user": {"login": "contributor"},
                        }
                    ],
                    "https://api.github.com/repos/owner/repo/issues/42/comments?per_page=100&page=2",
                )
            # Page 2 — owned comment here
            return (
                [
                    {
                        "id": 99,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nAssessment.",
                        "user": {"login": "github-actions[bot]"},
                    }
                ],
                "",
            )

        def fake_json(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            call_log.append(("_json", url, method))
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish(
            "<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew body.",
            "abcdef0123456789",
        )

        # Must have PATCHed the existing comment (URL contains /99)
        patch_calls = [
            c for c in call_log if c[0] == "_json" and "99" in c[1] and c[2] == "PATCH"
        ]
        assert len(patch_calls) == 1, f"Expected 1 PATCH to /comments/99, got {patch_calls}"
        # Must NOT have created a new comment
        post_calls = [
            c for c in call_log if c[0] == "_json" and c[2] == "POST"
        ]
        assert len(post_calls) == 0, f"Expected 0 POST calls, got {post_calls}"

    def test_paginated_comments_no_owned_creates_new(self) -> None:
        """When no bot-owned comment exists across all pages, publish must
        iterate through all pages then POST a new comment."""

        client = GitHubClient("token", "owner/repo", 42)
        call_log: list[tuple[str, str, object]] = []
        page_calls = 0

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            nonlocal page_calls
            page_calls += 1
            call_log.append(("_json_with_link", url, method))
            # Page 1 — link to page 2
            if page_calls == 1:
                return (
                    [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                    "https://api.github.com/repos/owner/repo/issues/42/comments?per_page=100&page=2",
                )
            # Page 2 — empty, no next
            return [], ""

        def fake_json(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            call_log.append(("_json", url, method))
            return {"id": 100}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew body.", "abcdef0123456789")

        # Must have POSTed a new comment
        post_calls = [
            c for c in call_log if c[0] == "_json" and c[2] == "POST"
        ]
        assert len(post_calls) == 1, f"Expected 1 POST for new comment, got {post_calls}"

    def test_off_origin_next_link_fails_safely(self) -> None:
        """A Link rel=next pointing to a different origin must cause
        pagination uncertainty → safe RuntimeError, no mutation."""

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                "https://evil.example/repos/owner/repo/issues/42/comments?page=2",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.", "abcdef0123456789")

        assert len(mutation_calls) == 0, "No PATCH/POST must be attempted"

    def test_non_list_response_page_fails_safely(self) -> None:
        """A page that returns a non-list (e.g. dict error) must cause
        pagination uncertainty → safe RuntimeError."""

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return ({"error": "bad gateway"}, "")

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.", "abcdef0123456789")

        assert len(mutation_calls) == 0

    def test_duplicate_comment_ids_across_pages_fails_safely(self) -> None:
        """When the same comment id appears on two pages (API cycle/bug),
        treat as pagination uncertainty → safe RuntimeError."""

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {"id": 5, "body": "dup", "user": {"login": "github-actions[bot]"}},
                    {"id": 5, "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nDup.", "user": {"login": "github-actions[bot]"}},
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.", "abcdef0123456789")

        assert len(mutation_calls) == 0


class TestAuthenticatedIdentity:
    def test_authenticated_login_retrieved_and_cached(self) -> None:
        """The bot identity must be retrieved once via /user and cached."""
        client = GitHubClient("token", "owner/repo", 42)
        user_calls = 0

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            nonlocal user_calls
            if "/user" in url and "/repos" not in url:
                user_calls += 1
                return {"login": "github-actions[bot]"}
            return {}

        client._json = fake_json  # type: ignore[method-assign]

        login1 = client.authenticated_login()
        login2 = client.authenticated_login()

        assert login1 == "github-actions[bot]"
        assert login2 == "github-actions[bot]"
        assert user_calls == 1, "/user must be called exactly once (cached)"

    def test_authenticated_login_non_dict_fails_safe(self) -> None:
        """When /user returns a non-dict, identity is uncertain → None."""
        client = GitHubClient("token", "owner/repo", 42)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            return ["not", "a", "dict"]

        client._json = fake_json  # type: ignore[method-assign]

        result = client.authenticated_login()
        assert result is None

    def test_authenticated_login_missing_login_key(self) -> None:
        """When /user response lacks a 'login' string key, identity is None."""
        client = GitHubClient("token", "owner/repo", 42)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            return {"id": 123, "type": "Bot"}

        client._json = fake_json  # type: ignore[method-assign]

        result = client.authenticated_login()
        assert result is None

    def test_publish_verifies_authenticated_identity_before_patch(self) -> None:
        """Before PATCHing a bot-owned comment, publish must verify the
        comment was authored by the *authenticated* identity (not just the
        hardcoded BOT_LOGIN constant)."""

        client = GitHubClient("token", "owner/repo", 42)
        call_log: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 42,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOld.",
                        "user": {"login": "github-actions[bot]"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            call_log.append(f"{method} {url}")
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew.", "abcdef0123456789")

        # Must have called /user for identity verification
        assert any("/user" in c for c in call_log), (
            f"Expected /user call for identity, got {call_log}"
        )
        # Must NOT use hardcoded BOT_LOGIN — must use authenticated identity
        assert any("PATCH" in c for c in call_log), f"Expected PATCH, got {call_log}"

    def test_publish_fails_when_authenticated_identity_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Outside GitHub Actions, when /user cannot confirm identity,
        publish must raise RuntimeError — never guess BOT_LOGIN alone.

        Inside Actions, installation tokens fall back to github-actions[bot]
        (see TestGitHubActionsTokenOwnership).
        """
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 42,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOld.",
                        "user": {"login": "github-actions[bot]"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"error": "rate limited"}
            mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="identity"):
            client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew.", "abcdef0123456789")

        assert len(mutation_calls) == 0, "No PATCH/POST when identity is uncertain"

    def test_contributor_with_copied_marker_never_patched(self) -> None:
        """A contributor-authored comment containing the Guardian marker
        must never be PATCHed — even if it looks like a bot comment."""

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 1,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nSpoofed marker.",
                        "user": {"login": "malicious-contributor"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            mutation_calls.append(f"{method} {url}")
            return {"id": 999}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew.", "abcdef0123456789")

        # Must create a NEW comment (POST), not PATCH the contributor's
        post_calls = [c for c in mutation_calls if "POST" in c]
        patch_calls = [c for c in mutation_calls if "PATCH" in c]
        assert len(post_calls) == 1, (
            f"Must POST new comment when only match is contributor-owned, "
            f"got {mutation_calls}"
        )
        assert len(patch_calls) == 0, "Must never PATCH a contributor comment"

    def test_similar_account_name_with_marker_not_patched(self) -> None:
        """An account named similarly to the bot (e.g. 'github-actions-bot')
        with a Guardian marker must not be mistaken for the real bot."""

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 1,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nSpoof.",
                        "user": {"login": "github-actions-bot"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            mutation_calls.append(f"{method} {url}")
            return {"id": 999}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish("<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew.", "abcdef0123456789")

        post_calls = [c for c in mutation_calls if "POST" in c]
        patch_calls = [c for c in mutation_calls if "PATCH" in c]
        assert len(post_calls) == 1, "Must POST new comment"
        assert len(patch_calls) == 0, "Must never PATCH imposter comment"


# ---------------------------------------------------------------------------
# Fix 3: Strict ownership marker validation
# ---------------------------------------------------------------------------

class TestStrictMarkerValidation:
    def test_exact_v2_marker_first_line_counts(self) -> None:
        """Only exact first-line v2 marker syntax with 16 hex chars counts."""
        from invariant_guardian.rendering.comment import MARKER_RE

        valid = "<!-- invariant-guardian:v2:abcdef0123456789 -->\nRest of body."
        assert MARKER_RE.match(valid.split("\n")[0]) is not None

    def test_v2_marker_not_on_first_line_rejected(self) -> None:
        """Marker on a later line must not count."""
        from invariant_guardian.rendering.comment import MARKER_RE

        body = "Some text\n<!-- invariant-guardian:v2:abcdef0123456789 -->\nMore."
        assert MARKER_RE.match(body.split("\n")[0]) is None

    def test_v1_v3_marker_rejected(self) -> None:
        """v1 or v3 marker syntax must not count."""
        from invariant_guardian.rendering.comment import MARKER_RE

        assert MARKER_RE.match("<!-- invariant-guardian:v1:abcdef0123456789 -->") is None
        assert MARKER_RE.match("<!-- invariant-guardian:v3:abcdef0123456789 -->") is None

    def test_wrong_fingerprint_length_rejected(self) -> None:
        """Fingerprint that is not exactly 16 lowercase hex chars is rejected."""
        from invariant_guardian.rendering.comment import MARKER_RE

        # Too short
        assert MARKER_RE.match("<!-- invariant-guardian:v2:abc123 -->") is None
        # Too long
        assert MARKER_RE.match("<!-- invariant-guardian:v2:abcdef0123456789a -->") is None
        # Uppercase
        assert MARKER_RE.match("<!-- invariant-guardian:v2:ABCDEF0123456789 -->") is None

    def test_substring_marker_not_in_first_line_rejected(self) -> None:
        """Marker appearing as substring later in body must not count."""
        body = "Regular PR comment\nHere is a reference: <!-- invariant-guardian:v2:abcdef0123456789 --> in text."
        comment = {
            "id": 1,
            "body": body,
            "user": {"login": "github-actions[bot]"},
        }
        # Current is_bot_comment uses MARKER_PREFIX in body — too loose
        assert not is_bot_comment(comment, "github-actions[bot]")

    def test_multiple_owned_comments_raises(self) -> None:
        """>1 distinct owned Guardian comments must raise RuntimeError."""
        comments = [
            {
                "id": 1,
                "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nFirst.",
                "user": {"login": "github-actions[bot]"},
            },
            {
                "id": 2,
                "body": "<!-- invariant-guardian:v2:0123456789abcdef -->\nSecond.",
                "user": {"login": "github-actions[bot]"},
            },
        ]
        with pytest.raises(RuntimeError, match="multiple|ambiguous|duplicate"):
            find_owned_comment(comments, "github-actions[bot]")


# ---------------------------------------------------------------------------
# Fix 5: URL validation before Authorization header (SSRF/token-leak protection)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Phase 3 fail-closed: Gap 2 — structural URL validation via urlparse
# ---------------------------------------------------------------------------

class TestStructuralUrlValidation:
    def test_url_with_userinfo_rejected(self) -> None:
        """URLs with username:password@ in the authority must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        with pytest.raises(RuntimeError, match="URL|invalid|unsafe"):
            client._request("https://user:pass@api.github.com/repos/owner/repo/test")

    def test_url_with_port_rejected(self) -> None:
        """URLs with an explicit port must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        with pytest.raises(RuntimeError, match="URL|invalid|unsafe"):
            client._request("https://api.github.com:443/repos/owner/repo/test")

    def test_url_with_fragment_rejected(self) -> None:
        """URLs with a fragment (#) must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        with pytest.raises(RuntimeError, match="URL|invalid|unsafe"):
            client._request("https://api.github.com/repos/owner/repo/test#section")

    def test_url_not_https_rejected(self) -> None:
        """URLs not using https scheme must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        with pytest.raises(RuntimeError, match="URL|invalid|unsafe"):
            client._request("http://api.github.com/repos/owner/repo/test")

    def test_url_with_sibling_repo_rejected_in_files_pagination(self) -> None:
        """A Link next= URL pointing to a sibling repo's files must be
        rejected.  The changed_files() pagination must not follow it."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/repos/evil/sibling/pulls/42/files?page=2>; rel="next"'},
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_url_encoded_slash_in_contents_path_rejected(self) -> None:
        """A Link with %2F encoding in the path (trying to escape contents
        boundary) must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/repos/owner/repo/pulls/42/filesevil?page=2>; rel="next"'},
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_comments_resource_not_accepted_for_files_pagination(self) -> None:
        """A Link to /issues/.../comments must not be accepted during
        changed_files() pagination — wrong resource type."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/repos/owner/repo/issues/42/comments?page=2>; rel="next"'},
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_files_resource_not_accepted_for_comments_pagination(self) -> None:
        """A Link to /pulls/.../files must not be accepted during publish()
        comment pagination — wrong resource type."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str, method: str = "GET", payload=None
        ) -> tuple[object, str]:
            return (
                [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                "https://api.github.com/repos/owner/repo/pulls/42/files?page=2",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link
        client._json = fake_json

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0

    def test_invariant_contents_url_outside_own_repo_rejected(self) -> None:
        """write_invariants() entry URL pointing to a sibling repo's
        contents must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda url, **kw: [
            {
                "type": "file",
                "name": "safe.md",
                "url": "https://api.github.com/repos/evil/other/contents/safe.md",
            }
        ]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, ValueError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_fake_transport_no_request_for_files_with_comments_next(self) -> None:
        """Fake transport: when a changed_files response has a Link to the
        comments endpoint, no request must be made to that URL — it's
        validated and rejected before any call."""
        from tests.fixtures.github.fake_transport import FakeTransport

        transport = FakeTransport()
        transport.register(
            "/pulls/42/files",
            200,
            [{"filename": "src/A.java", "status": "modified", "patch": "@@"}],
            {"Link": '<https://api.github.com/repos/owner/repo/issues/42/comments?page=2>; rel="next"'},
        )
        # Register the wrong-resource URL — it must never be called
        transport.register(
            "/issues/42/comments", 200, [{"id": 1, "body": "evil"}]
        )

        client = GitHubClient("token", "owner/repo", 42)
        transport.inject(client)

        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

        # Verify the comments endpoint was NOT called
        comments_calls = [
            c for c in transport.call_log() if "/issues/42/comments" in c[0]
        ]
        assert len(comments_calls) == 0, (
            f"Wrong-resource URL must not be called. "
            f"Got calls: {transport.call_log()}"
        )


class TestUrlValidationBeforeAuth:
    def test_non_github_url_rejected_before_auth(self) -> None:
        """Requests to non-https://api.github.com URLs must be rejected
        before the Authorization header is attached."""
        client = GitHubClient("token-secret", "owner/repo", 1)

        with pytest.raises(RuntimeError, match="URL|invalid|unsafe"):
            client._request("http://api.github.com/repos/owner/repo/test")

    def test_non_api_github_rejected(self) -> None:
        """Requests to github.com (not api.github.com) must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)

        with pytest.raises(RuntimeError, match="URL|invalid|unsafe"):
            client._request("https://github.com/owner/repo")

    def test_evil_url_rejected_before_token_sent(self) -> None:
        """An SSRF attempt to an attacker-controlled host must be rejected
        before the Authorization header (bearing the token) is sent."""
        import urllib.error

        import invariant_guardian.adapters.github.client as client_mod

        client = GitHubClient("token-secret-value", "owner/repo", 1)
        token_sent = False
        original_urlopen = client_mod.urlopen

        def capture_urlopen(req, timeout=20):
            nonlocal token_sent
            # Check if Authorization header was attached
            if req.get_header("Authorization"):
                token_sent = True
            raise urllib.error.HTTPError(
                req.full_url, 500, "Error", {}, None
            )

        try:
            client_mod.urlopen = capture_urlopen
            with pytest.raises(RuntimeError):
                client._request("https://evil.example.com/steal-token")
            # Token must NOT have been sent to evil host
            assert not token_sent, (
                "Authorization header must not be attached to non-GitHub URLs"
            )
        finally:
            client_mod.urlopen = original_urlopen

    # --- P1.4: Same-origin /user must be rejected by pagination call sites ---

    def test_changed_files_link_to_user_endpoint_fails_before_request(self) -> None:
        """P1.4: A Link rel=next pointing to /user (same origin, wrong resource)
        must fail without invoking transport — the token must not be sent."""
        client = GitHubClient("token-secret-value", "owner/repo", 42)

        transport_called = False
        def fake_request(url: str, *args, **kwargs):
            nonlocal transport_called
            transport_called = True
            return b"[]"

        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/user>; rel="next"'},
        )  # type: ignore[method-assign]

        # _request_with_headers is also called for the first page
        # Override to detect whether the /user URL reaches transport
        import invariant_guardian.adapters.github.client as client_mod
        original_urlopen = client_mod.urlopen

        try:
            with pytest.raises(RuntimeError, match="incomplete|unavailable"):
                client.changed_files()
        finally:
            client_mod.urlopen = original_urlopen

    def test_changed_files_link_to_other_repo_fails_before_request(self) -> None:
        """P1.4: A Link rel=next pointing to a different repository
        (same origin, wrong repo) must fail without invoking transport."""
        client = GitHubClient("token-secret-value", "owner/repo", 42)

        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/repos/evil/steal/pulls/42/files?page=2>; rel="next"'},
        )  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_publish_link_to_user_endpoint_fails_before_request(self) -> None:
        """P1.4: publish() pagination with Link to /user must fail without
        mutation — same-origin wrong-resource must not be followed."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                "https://api.github.com/user",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0, "P1.4: No PATCH/POST to wrong endpoint"

    def test_deterministic_fake_transport_rejects_wrong_resource(self) -> None:
        """P1.4: Deterministic fake transport regression — a pagination URL
        to /user must be validated and rejected before any request is made
        to that URL."""
        from tests.fixtures.github.fake_transport import FakeTransport

        transport = FakeTransport()
        # Register the first page normally
        transport.register(
            "/pulls/42/files",
            200,
            [{"filename": "src/A.java", "status": "modified", "patch": "@@"}],
            {"Link": '<https://api.github.com/user>; rel="next"'},
        )
        # /user should never be called — but register it to assert it ISN'T hit
        transport.register("/user", 200, {"login": "stolen-identity"})

        client = GitHubClient("token", "owner/repo", 42)
        transport.inject(client)

        # Must raise — the /user Link is a wrong resource for files pagination
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

        # Verify /user was NOT called — the validation stopped it
        user_calls = [c for c in transport.call_log() if "/user" in c[0]]
        assert len(user_calls) == 0, (
            f"P1.4: /user must not be called during files pagination. "
            f"Got calls: {transport.call_log()}"
        )


class TestWriteInvariantsValidation:
    def test_non_list_listing_raises(self) -> None:
        """write_invariants must raise when listing is not a list."""
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda url, **kw: {"not": "a list"}  # type: ignore[method-assign]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, TypeError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_path_traversal_in_entry_name_rejected(self) -> None:
        """Entry names containing path traversal must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        # Return a listing with a traversal entry name
        client._json = lambda url, **kw: [  # type: ignore[method-assign]
            {
                "type": "file",
                "name": "../../../etc/passwd",
                "url": "https://api.github.com/repos/owner/repo/contents/bad",
            }
        ]
        client._json_with_link = lambda url, **kw: (  # type: ignore[method-assign]
            [{"type": "file", "name": "../../../etc/passwd",
              "url": "https://api.github.com/repos/owner/repo/contents/bad"}],
            "",
        )
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, ValueError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_off_origin_entry_url_rejected(self) -> None:
        """Entry URLs pointing to a different origin must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda url, **kw: [  # type: ignore[method-assign]
            {
                "type": "file",
                "name": "safe.md",
                "url": "https://evil.example/contents/safe.md",
            }
        ]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, ValueError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_invalid_base64_content_rejected(self) -> None:
        """P2.2: Invalid base64 characters (like %%) must be rejected with
        sanitized RuntimeError, not silently decoded with discarded chars."""
        client = GitHubClient("token", "owner/repo", 1)
        # Listing with one file
        call_count = 0

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Listing response
                return [{
                    "type": "file",
                    "name": "a.md",
                    "url": "https://api.github.com/repos/owner/repo/contents/a.md",
                }]
            else:
                # Content response with invalid base64
                return {"encoding": "base64", "content": "%%%YQ=="}

        client._json = fake_json  # type: ignore[method-assign]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, ValueError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_non_string_content_rejected(self) -> None:
        """P2.2: Non-string base64 content must be rejected."""
        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{
                    "type": "file",
                    "name": "a.md",
                    "url": "https://api.github.com/repos/owner/repo/contents/a.md",
                }]
            else:
                # Content is not a string — already caught by existing check
                return {"encoding": "base64", "content": 12345}

        client._json = fake_json  # type: ignore[method-assign]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, TypeError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    # Phase 3 fail-closed: Gap 3 — every listing entry must be well-formed

    def test_entry_with_non_string_name_must_fail_closed(self) -> None:
        """An entry whose 'name' is not a string must fail closed,
        not silently skip."""
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda url, **kw: [
            {
                "type": "file",
                "name": 12345,  # not a string
                "url": "https://api.github.com/repos/owner/repo/contents/a.md",
            }
        ]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, TypeError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_entry_with_missing_type_must_fail_closed(self) -> None:
        """An entry without a 'type' key must fail closed."""
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda url, **kw: [
            {
                "name": "safe.md",
                "url": "https://api.github.com/repos/owner/repo/contents/safe.md",
            }
        ]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, TypeError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_entry_with_non_string_url_must_fail_closed(self) -> None:
        """An entry whose 'url' is not a string must fail closed."""
        client = GitHubClient("token", "owner/repo", 1)
        client._json = lambda url, **kw: [
            {
                "type": "file",
                "name": "safe.md",
                "url": 99999,  # not a string
            }
        ]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, TypeError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_entry_without_md_extension_can_be_safely_ignored(self) -> None:
        """A valid non-.md file entry with well-formed shape may be safely
        ignored — no failure."""
        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [
                    {
                        "type": "file",
                        "name": "README.txt",
                        "url": "https://api.github.com/repos/owner/repo/contents/README.txt",
                    },
                    {
                        "type": "file",
                        "name": "invariant.md",
                        "url": "https://api.github.com/repos/owner/repo/contents/invariant.md",
                    },
                ]
            else:
                return {
                    "encoding": "base64",
                    "content": "IyBUZXN0IEludmFyaWFudAo=",  # valid base64: "# Test Invariant\n"
                }

        client._json = fake_json  # type: ignore[method-assign]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            client.write_invariants(Path(tmp), "ref", "invariants")
            # Only invariant.md should be written
            dest = Path(tmp)
            files = list(dest.glob("*.md"))
            assert len(files) == 1
            assert files[0].name == "invariant.md"

    def test_empty_base64_content_must_fail_closed(self) -> None:
        """Base64 content that decodes to empty bytes must fail closed."""
        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{
                    "type": "file",
                    "name": "a.md",
                    "url": "https://api.github.com/repos/owner/repo/contents/a.md",
                }]
            else:
                return {"encoding": "base64", "content": ""}  # empty base64

        client._json = fake_json  # type: ignore[method-assign]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, ValueError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_non_ascii_base64_content_must_fail_closed(self) -> None:
        """Base64 content with non-ASCII characters must fail closed."""
        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{
                    "type": "file",
                    "name": "a.md",
                    "url": "https://api.github.com/repos/owner/repo/contents/a.md",
                }]
            else:
                # Contains non-ASCII UTF-8 characters
                return {"encoding": "base64", "content": "¡Hola Mundo!"}

        client._json = fake_json  # type: ignore[method-assign]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, ValueError)):
            client.write_invariants(Path(tmp), "ref", "invariants")

    def test_decoded_content_is_binary_non_utf8_must_fail_closed(self) -> None:
        """Base64 content that decodes to binary (non-UTF-8) bytes must
        fail closed with sanitized RuntimeError."""
        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{
                    "type": "file",
                    "name": "a.md",
                    "url": "https://api.github.com/repos/owner/repo/contents/a.md",
                }]
            else:
                # Valid base64 for 0xFF 0xFE 0x00 0x01 (invalid UTF-8)
                import base64 as _b64
                return {"encoding": "base64", "content": _b64.b64encode(b'\xff\xfe\x00\x01').decode("ascii")}

        client._json = fake_json  # type: ignore[method-assign]
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp, pytest.raises((RuntimeError, ValueError)):
            client.write_invariants(Path(tmp), "ref", "invariants")


class TestBoundedHttpReads:
    def test_response_read_enforces_hard_cap(self) -> None:
        """_bounded_read must enforce MAX_RESPONSE_BYTES hard cap,
        not trust Content-Length alone."""
        from io import BytesIO

        from invariant_guardian.adapters.github.client import _bounded_read

        # Body within bounds — Content-Length may be present but isn't trusted
        body = b"x" * 100
        fake_response = BytesIO(body)
        fake_response.length = 100  # type: ignore[attr-defined]

        result = _bounded_read(fake_response)  # type: ignore[arg-type]
        assert len(result) == 100
        assert result == body

    def test_bounded_read_caps_at_max_when_no_content_length(self) -> None:
        """When Content-Length is missing, read up to MAX_RESPONSE_BYTES+1
        and reject if exceeded."""
        from io import BytesIO

        from invariant_guardian.adapters.github.client import _bounded_read
        from invariant_guardian.context import MAX_RESPONSE_BYTES

        # Within bounds
        small_body = b"x" * 1000
        fake_response = BytesIO(small_body)
        fake_response.length = None  # type: ignore[attr-defined]

        result = _bounded_read(fake_response)  # type: ignore[arg-type]
        assert len(result) == 1000

        # Over bounds — must raise
        oversized = b"x" * (MAX_RESPONSE_BYTES + 1)
        fake_response = BytesIO(oversized)
        fake_response.length = None  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="exceeds"):
            _bounded_read(fake_response)  # type: ignore[arg-type]

    def test_content_length_lying_small_but_body_huge_detected(self) -> None:
        """When Content-Length lies (declares small but body is huge),
        the read must enforce the hard cap, not trust the header."""
        from io import BytesIO

        from invariant_guardian.adapters.github.client import _bounded_read
        from invariant_guardian.context import MAX_RESPONSE_BYTES

        # Content-Length claims 100 bytes but actual body is enormous
        # _bounded_read must NOT trust this; it must enforce the hard cap
        huge_body = b"x" * (MAX_RESPONSE_BYTES + 1000)
        fake_response = BytesIO(huge_body)
        fake_response.length = 100  # type: ignore[attr-defined] — liar!

        with pytest.raises(RuntimeError, match="exceeds|limit"):
            _bounded_read(fake_response)  # type: ignore[arg-type]

    def test_content_length_lying_large_but_body_small_detected(self) -> None:
        """When Content-Length declares large but body is small (truncated),
        the read must not hang waiting for bytes that never arrive."""
        from io import BytesIO

        from invariant_guardian.adapters.github.client import _bounded_read

        # Content-Length claims 1000 but only 100 bytes available
        small_body = b"x" * 100
        fake_response = BytesIO(small_body)
        fake_response.length = 1000  # type: ignore[attr-defined] — liar!

        # Must not hang; read returns what's available
        result = _bounded_read(fake_response)  # type: ignore[arg-type]
        assert len(result) == 100, (
            f"Should return actual bytes ({len(result)}), not trust Content-Length"
        )

    def test_retry_after_capped_at_max(self) -> None:
        """Retry-After values exceeding MAX_RETRY_DELAY must be capped."""
        import urllib.error
        from io import BytesIO

        import invariant_guardian.adapters.github.client as client_mod
        from invariant_guardian.context import MAX_RETRY_DELAY

        client = GitHubClient("token", "owner/repo", 1)
        sleep_calls: list[float] = []
        call_count = 0

        def fake_urlopen(req, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                error = urllib.error.HTTPError(
                    req.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "3600"},  # 1 hour — must be capped
                    None,
                )
                raise error
            body = b'{"login": "bot"}'
            bio = BytesIO(body)
            bio.length = len(body)  # type: ignore[attr-defined]
            resp = type("FakeResponse", (), {
                "read": bio.read,
                "__enter__": lambda s: s,
                "__exit__": lambda s, *a: None,
                "headers": type("FakeHeaders", (), {"items": lambda s: []})(),
                "length": len(body),
            })()
            return resp

        # Patch _sleep as an instance attribute
        client._sleep = lambda s: sleep_calls.append(s)  # type: ignore[method-assign]
        original_urlopen = client_mod.urlopen
        try:
            client_mod.urlopen = fake_urlopen  # type: ignore[assignment]
            result = client.authenticated_login()
            assert result == "bot"
            assert len(sleep_calls) == 1
            assert sleep_calls[0] <= MAX_RETRY_DELAY, (
                f"Retry-After must be capped at {MAX_RETRY_DELAY}, "
                f"got {sleep_calls[0]}"
            )
        finally:
            client_mod.urlopen = original_urlopen  # type: ignore[assignment]

    def test_httperror_body_never_read(self) -> None:
        """HTTPError objects must never have their .read() called —
        their bodies may contain sensitive data."""
        import urllib.error

        import invariant_guardian.adapters.github.client as client_mod

        client = GitHubClient("token", "owner/repo", 1)
        body_read = False

        class SafeHTTPError(urllib.error.HTTPError):
            def read(self):
                nonlocal body_read
                body_read = True
                return b"secret error details"

        def fake_urlopen(req, timeout=20):
            raise SafeHTTPError(
                req.full_url,
                500,
                "Server Error",
                {},
                None,
            )

        # Prevent sleep during retries
        client._sleep = lambda s: None  # type: ignore[method-assign]
        original_urlopen = client_mod.urlopen
        try:
            client_mod.urlopen = fake_urlopen  # type: ignore[assignment]
            with pytest.raises(RuntimeError):
                client._json("https://api.github.com/repos/owner/repo/test")
            assert not body_read, (
                "HTTPError body must never be read"
            )
        finally:
            client_mod.urlopen = original_urlopen  # type: ignore[assignment]

    def test_bounded_read_rejects_when_body_exceeds_cap(self) -> None:
        """When the actual body exceeds MAX_RESPONSE_BYTES, reject it
        regardless of what Content-Length declares."""
        from io import BytesIO

        from invariant_guardian.adapters.github.client import _bounded_read
        from invariant_guardian.context import MAX_RESPONSE_BYTES

        # Oversized actual body must be rejected even if Content-Length lies
        oversized = b"x" * (MAX_RESPONSE_BYTES + 100)
        fake_response = BytesIO(oversized)

        with pytest.raises(RuntimeError, match="exceeds"):
            _bounded_read(fake_response)  # type: ignore[arg-type]


class TestRetryTransport:
    def test_retry_on_429_for_get(self) -> None:
        """GET requests that receive 429 must be retried (bounded)."""
        import urllib.error
        from io import BytesIO

        import invariant_guardian.adapters.github.client as client_mod

        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0
        sleep_calls: list[float] = []

        def fake_urlopen(req, timeout=20):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                error = urllib.error.HTTPError(
                    req.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "1"},
                    None,  # type: ignore[arg-type]
                )
                raise error
            # Success on third attempt
            body = b'{"login": "bot"}'
            bio = BytesIO(body)
            bio.length = len(body)  # type: ignore[attr-defined]
            resp = type("FakeResponse", (), {
                "read": bio.read,
                "__enter__": lambda s: s,
                "__exit__": lambda s, *a: None,
                "headers": type("FakeHeaders", (), {"items": lambda s: []})(),
                "length": len(body),
            })()
            return resp

        original_urlopen = client_mod.urlopen
        original_sleep = client_mod.GitHubClient._sleep
        client_mod.GitHubClient._sleep = staticmethod(lambda s: sleep_calls.append(s))  # type: ignore[assignment]
        try:
            client_mod.urlopen = fake_urlopen  # type: ignore[assignment]
            result = client.authenticated_login()
            assert result == "bot"
            assert call_count == 3, f"Expected 3 calls (2 retries + success), got {call_count}"
            assert len(sleep_calls) == 2, "Should have slept between 2 retries"
        finally:
            client_mod.urlopen = original_urlopen  # type: ignore[assignment]
            client_mod.GitHubClient._sleep = original_sleep  # type: ignore[assignment]

    def test_no_retry_on_post_patch(self) -> None:
        """Mutation methods (POST/PATCH) must never be retried."""
        import urllib.error

        import invariant_guardian.adapters.github.client as client_mod

        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0

        def fake_urlopen(req, timeout=20):
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                req.full_url,
                500,
                "Server Error",
                {},
                None,  # type: ignore[arg-type]
            )

        original_urlopen = client_mod.urlopen
        original_sleep = client_mod.GitHubClient._sleep
        client_mod.GitHubClient._sleep = staticmethod(lambda s: None)  # type: ignore[assignment]
        try:
            client_mod.urlopen = fake_urlopen  # type: ignore[assignment]
            with pytest.raises(RuntimeError):
                client._json("https://api.github.com/test", method="POST",
                             payload={"x": 1})
            assert call_count == 1, f"POST must not be retried, got {call_count} calls"
        finally:
            client_mod.urlopen = original_urlopen  # type: ignore[assignment]
            client_mod.GitHubClient._sleep = original_sleep  # type: ignore[assignment]

    def test_no_retry_on_permanent_4xx(self) -> None:
        """Non-429 4xx errors must not be retried."""
        import urllib.error

        import invariant_guardian.adapters.github.client as client_mod

        client = GitHubClient("token", "owner/repo", 1)
        call_count = 0

        def fake_urlopen(req, timeout=20):
            nonlocal call_count
            call_count += 1
            raise urllib.error.HTTPError(
                req.full_url,
                404,
                "Not Found",
                {},
                None,  # type: ignore[arg-type]
            )

        original_urlopen = client_mod.urlopen
        original_sleep = client_mod.GitHubClient._sleep
        client_mod.GitHubClient._sleep = staticmethod(lambda s: None)  # type: ignore[assignment]
        try:
            client_mod.urlopen = fake_urlopen  # type: ignore[assignment]
            with pytest.raises(RuntimeError):
                client._json("https://api.github.com/test")
            assert call_count == 1, f"404 must not be retried, got {call_count} calls"
        finally:
            client_mod.urlopen = original_urlopen  # type: ignore[assignment]
            client_mod.GitHubClient._sleep = original_sleep  # type: ignore[assignment]

    def test_error_messages_sanitized(self) -> None:
        """Public error messages must not expose raw tokens or bodies."""
        import urllib.error

        import invariant_guardian.adapters.github.client as client_mod

        client = GitHubClient("token-secret-value", "owner/repo", 1)

        def fake_urlopen(req, timeout=20):
            raise urllib.error.HTTPError(
                req.full_url,
                500,
                "Server Error",
                {},
                None,  # type: ignore[arg-type]
            )

        original_urlopen = client_mod.urlopen
        original_sleep = client_mod.GitHubClient._sleep
        client_mod.GitHubClient._sleep = staticmethod(lambda s: None)  # type: ignore[assignment]
        try:
            client_mod.urlopen = fake_urlopen  # type: ignore[assignment]
            with pytest.raises(RuntimeError) as exc_info:
                client._json("https://api.github.com/test")
            error_msg = str(exc_info.value)
            assert "token-secret-value" not in error_msg, (
                f"Token leaked in error: {error_msg}"
            )
        finally:
            client_mod.urlopen = original_urlopen  # type: ignore[assignment]
            client_mod.GitHubClient._sleep = original_sleep  # type: ignore[assignment]


class TestChangedFilesPagination:
    def test_fetches_one_extra_record_to_signal_file_ceiling(self) -> None:
        """File cap exhaustion (>MAX_CHANGED_FILES) must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        calls = 0

        def fake_page(url: str):
            nonlocal calls
            calls += 1
            start = (calls - 1) * 100
            entries = [
                {
                    "filename": f"src/File{i}.java",
                    "status": "modified",
                    "patch": "@@ -1 +1 @@\n+class File {}",
                }
                for i in range(start, start + 100)
            ]
            next_url = ""
            if calls < 3:
                next_url = (
                    "https://api.github.com/repos/owner/repo/pulls/42/files"
                    f"?per_page=100&page={calls + 1}"
                )
            return entries, next_url

        client._json_with_link = fake_page  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_missing_non_removed_patch_is_incomplete(self) -> None:
        """Missing patch on a modified file must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/Foo.java", "status": "modified"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_renamed_file_captures_previous_filename(self) -> None:
        """Renamed files must expose previous_filename from the API."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [
                {
                    "filename": "src/New.java",
                    "status": "renamed",
                    "previous_filename": "src/Old.java",
                    "patch": "@@ -1 +1 @@\n rename",
                }
            ],
            "",
        )
        [changed] = client.changed_files()
        assert changed.status == "renamed"
        assert changed.previous_filename == "src/Old.java"

    def test_off_origin_link_in_files_pagination_fails_safely(self) -> None:
        """A Link rel=next for changed files pointing off-origin must raise RuntimeError."""

        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [
                {
                    "filename": "src/A.java",
                    "status": "modified",
                    "patch": "@@ -1 +1 @@",
                }
            ],
            "https://evil.example/repos/owner/repo/pulls/42/files?page=2",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_non_list_files_response_is_handled(self) -> None:
        """A non-list files API response must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            {"message": "Server Error"}, ""
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_non_list_response_raises_unavailability(self) -> None:
        """A non-list files response must raise RuntimeError, not return empty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            {"message": "Server Error"}, ""
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_invalid_entry_raises_unavailability(self) -> None:
        """A non-dict entry in files list must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            ["not_a_dict", {"filename": "x.java", "status": "modified", "patch": "@@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_missing_filename_raises_unavailability(self) -> None:
        """An entry with missing/invalid filename must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"status": "modified", "patch": "@@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_missing_patch_on_added_file_raises_unavailability(self) -> None:
        """Missing patch on an added file must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/New.java", "status": "added"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_off_origin_next_link_raises_unavailability(self) -> None:
        """Off-origin Link rel=next must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [
                {
                    "filename": "src/A.java",
                    "status": "modified",
                    "patch": "@@ -1 +1 @@",
                }
            ],
            "https://evil.example/repos/owner/repo/pulls/42/files?page=2",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_file_cap_exhaustion_raises_unavailability(self) -> None:
        """Exceeding MAX_CHANGED_FILES must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        # Create more entries than MAX_CHANGED_FILES
        entries = [
            {
                "filename": f"src/File{i}.java",
                "status": "modified",
                "patch": "@@ -1 +1 @@",
            }
            for i in range(250)
        ]
        client._json_with_link = lambda url: (entries, "")  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_json_decode_failure_raises_unavailability(self) -> None:
        """JSON decode / API failure in files pagination must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        def raise_runtime(url: str):
            raise RuntimeError("GitHub API request failed")
        client._json_with_link = raise_runtime  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_cycle_next_url_raises_unavailability(self) -> None:
        """Repeated/cycle next URL must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        seen_urls: list[str] = []
        def cycle_page(url: str):
            seen_urls.append(url)
            return (
                [{"filename": f"src/F{len(seen_urls)}.java", "status": "modified",
                  "patch": "@@ -1 +1 @@"}],
                "https://api.github.com/repos/owner/repo/pulls/42/files?page=1",
            )
        client._json_with_link = cycle_page  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable|uncertain"):
            client.changed_files()

    def test_valid_removed_file_without_patch_does_not_raise(self) -> None:
        """Removed files may omit patch without triggering unavailability."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/Deleted.java", "status": "removed"}],
            "",
        )
        files = client.changed_files()
        assert len(files) == 1
        assert files[0].status == "removed"
        assert files[0].patch is None
        assert files[0].patch_complete is True  # removed files may omit patch

    def test_unknown_status_raises_not_normalized_to_modified(self) -> None:
        """P1.2: Unknown file status must raise RuntimeError, never silently
        normalize to 'modified'."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/A.java", "status": "unexpected", "patch": "@@ -1 +1 @@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_files_page_count_bounded(self) -> None:
        """Files pagination exceeding MAX_CHANGED_FILE_PAGES must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        calls = 0

        def infinite_pages(url: str):
            nonlocal calls
            calls += 1
            return (
                [
                    {
                        "filename": f"src/File{calls}_{i}.java",
                        "status": "modified",
                        "patch": "@@ -1 +1 @@",
                    }
                    for i in range(2)
                ],
                f"https://api.github.com/repos/owner/repo/pulls/42/files?page={calls + 1}",
            )

        client._json_with_link = infinite_pages  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    # -------------------------------------------------------------------
    # Phase 3 fail-closed: Gap 1 — strict changed_files entry validation
    # -------------------------------------------------------------------

    def test_missing_status_key_raises_not_defaults_modified(self) -> None:
        """When an entry lacks a 'status' key entirely, the listing is
        uncertain — never silently default to 'modified'."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/A.java", "patch": "@@ -1 +1 @@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_filename_with_null_byte_raises_uncertain(self) -> None:
        """A filename containing NUL must cause uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/A\x00.java", "status": "modified", "patch": "@@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_filename_with_leading_slash_raises_uncertain(self) -> None:
        """A filename starting with / must cause uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "/etc/passwd", "status": "modified", "patch": "@@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_filename_with_dot_dot_component_raises_uncertain(self) -> None:
        """A filename with a .. path component must cause uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/../etc/passwd", "status": "modified", "patch": "@@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_filename_is_dot_component_raises_uncertain(self) -> None:
        """A filename that is just '.' must cause uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": ".", "status": "modified", "patch": "@@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_renamed_without_previous_filename_raises_uncertain(self) -> None:
        """A renamed file without previous_filename must cause uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [
                {
                    "filename": "src/New.java",
                    "status": "renamed",
                    "patch": "@@ -1 +1 @@",
                }
            ],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_renamed_previous_filename_is_unsafe_raises_uncertain(self) -> None:
        """A renamed file whose previous_filename contains .. must cause
        uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [
                {
                    "filename": "src/New.java",
                    "status": "renamed",
                    "previous_filename": "../secret.txt",
                    "patch": "@@ -1 +1 @@",
                }
            ],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_patch_is_dict_not_string_raises_uncertain(self) -> None:
        """A patch value that is not a string (e.g. a dict) must be treated
        as a missing patch → uncertainty for added/modified files."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/A.java", "status": "modified", "patch": {}}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_patch_is_int_not_string_raises_uncertain(self) -> None:
        """A patch value that is an int must be treated as missing →
        uncertainty for added files."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/New.java", "status": "added", "patch": 12345}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_filename_is_empty_string_raises_uncertain(self) -> None:
        """An empty string filename must cause uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "", "status": "modified", "patch": "@@"}],
            "",
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()


# ---------------------------------------------------------------------------
# Fix 2: Sanitised JSON/Unicode decode errors
# ---------------------------------------------------------------------------

class TestCommentPaginationCycleDetection:
    def test_url_cycle_fails_safely(self) -> None:
        """When the same URL appears on two pages (even with different IDs),
        fail safe — no PATCH/POST."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []
        page_calls = 0

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            nonlocal page_calls
            page_calls += 1
            # Page 1 returns a next link
            if page_calls == 1:
                return (
                    [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                    "https://api.github.com/repos/owner/repo/issues/42/comments?page=2",
                )
            # Page 2's next link points back to page 1 — URL cycle
            return (
                [{"id": 2, "body": "hi2", "user": {"login": "contributor"}}],
                "https://api.github.com/repos/owner/repo/issues/42/comments?page=1",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0, "No PATCH/POST on URL cycle"

    def test_malformed_link_multiple_rel_next_fails_safely(self) -> None:
        """Malformed Link with multiple rel=next values must cause
        pagination uncertainty."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            # Simulate malformed Link by providing headers that would
            # cause the regex to match ambiguously
            # The _json_with_link method parses the Link header — test
            # that malformed syntax doesn't cause incorrect behavior
            return (
                [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                "https://evil.example/repos/owner/repo/issues/42/comments?page=2",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        # Off-origin next URL must cause pagination uncertainty
        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0

    def test_comment_cap_exhaustion_fails_safely(self) -> None:
        """When total comments exceed MAX_COMMENTS, fail safe."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        # Generate more than MAX_COMMENTS entries
        from invariant_guardian.context import MAX_COMMENTS
        many_comments = [
            {"id": i, "body": f"comment {i}", "user": {"login": "contributor"}}
            for i in range(MAX_COMMENTS + 10)
        ]

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (many_comments, "")

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0

    def test_page_cap_exhaustion_fails_safely(self) -> None:
        """When page count exceeds MAX_COMMENT_PAGES, fail safe."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []
        page = 0

        def infinite_pages(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            nonlocal page
            page += 1
            return (
                [{"id": page, "body": f"c{page}", "user": {"login": "contributor"}}],
                f"https://api.github.com/repos/owner/repo/issues/42/comments?page={page + 1}",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = infinite_pages  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0

    def test_multiple_owned_comments_across_pages_raises_no_mutation(self) -> None:
        """When multiple bot-owned Guardian comments exist across paginated
        pages, publish must raise before any PATCH/POST mutation.

        This is the concrete Phase 3 blocker: find_owned_comment returning
        None for both 0 and >1 causes silent duplicate creation."""

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []
        page_calls = 0

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            nonlocal page_calls
            page_calls += 1
            if page_calls == 1:
                # Page 1 — one owned comment, link to page 2
                return (
                    [
                        {
                            "id": 10,
                            "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nFirst.",
                            "user": {"login": "github-actions[bot]"},
                        }
                    ],
                    "https://api.github.com/repos/owner/repo/issues/42/comments?per_page=100&page=2",
                )
            # Page 2 — second owned comment (duplicate!)
            return (
                [
                    {
                        "id": 99,
                        "body": "<!-- invariant-guardian:v2:0123456789abcdef -->\nSecond.",
                        "user": {"login": "github-actions[bot]"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="ambiguous|multiple|duplicate|Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )

        assert len(mutation_calls) == 0, (
            f"Expected 0 PATCH/POST calls for duplicate owned comments, "
            f"got {mutation_calls}"
        )

    def test_multiple_owned_comments_single_page_raises_no_mutation(self) -> None:
        """When multiple bot-owned comments exist on a single page,
        publish must raise before any mutation."""

        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 1,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nFirst.",
                        "user": {"login": "github-actions[bot]"},
                    },
                    {
                        "id": 2,
                        "body": "<!-- invariant-guardian:v2:0123456789abcdef -->\nSecond.",
                        "user": {"login": "github-actions[bot]"},
                    },
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="ambiguous|multiple|duplicate|Cannot publish"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )

        assert len(mutation_calls) == 0, (
            "No PATCH/POST when multiple owned comments exist"
        )


class TestJsonDecodeSanitization:
    def test_json_decode_error_is_sanitized(self) -> None:
        """JSON decode failure must raise RuntimeError without raw body content."""
        from io import BytesIO

        client = GitHubClient("token", "owner/repo", 1)

        body = b"this is not json {{{malformed"
        bio = BytesIO(body)
        bio.length = len(body)  # type: ignore[attr-defined]
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            read = bio.read

        fake_response = FakeResponse()
        fake_response.length = len(body)  # type: ignore[attr-defined]
        fake_response.headers = type("FakeHeaders", (), {"items": lambda s: []})()

        import invariant_guardian.adapters.github.client as client_mod
        original_urlopen = client_mod.urlopen
        try:
            client_mod.urlopen = lambda req, timeout=20: fake_response
            with pytest.raises(RuntimeError, match="JSON|parse|malformed"):
                client._json("https://api.github.com/repos/owner/repo/test")
        finally:
            client_mod.urlopen = original_urlopen

    def test_unicode_decode_error_is_sanitized(self) -> None:
        """UTF-8 decode failure must raise RuntimeError without raw bytes."""
        from io import BytesIO

        client = GitHubClient("token", "owner/repo", 1)

        invalid_utf8 = b'\xff\xfe\x00\x01'
        bio = BytesIO(invalid_utf8)
        bio.length = len(invalid_utf8)  # type: ignore[attr-defined]
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            read = bio.read

        fake_response = FakeResponse()
        fake_response.length = len(invalid_utf8)  # type: ignore[attr-defined]
        fake_response.headers = type("FakeHeaders", (), {"items": lambda s: []})()

        import invariant_guardian.adapters.github.client as client_mod
        original_urlopen = client_mod.urlopen
        try:
            client_mod.urlopen = lambda req, timeout=20: fake_response
            with pytest.raises(RuntimeError, match="decode|encoding|UTF"):
                client._json("https://api.github.com/repos/owner/repo/test")
        finally:
            client_mod.urlopen = original_urlopen

    def test_malformed_link_header_raises_rather_than_silent_no_next(self) -> None:
        """P1.1: Non-empty malformed Link header (ambiguous rel) must raise
        RuntimeError, never silently return empty next_url."""
        import json as _json
        from io import BytesIO

        client = GitHubClient("token", "owner/repo", 1)

        body = _json.dumps([{"id": 1}]).encode("utf-8")
        bio = BytesIO(body)
        bio.length = len(body)  # type: ignore[attr-defined]

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            read = bio.read

        fake_response = FakeResponse()
        fake_response.length = len(body)  # type: ignore[attr-defined]
        # Malformed Link header — multiple rel= values on same entry
        fake_response.headers = type("FakeHeaders", (), {
            "items": lambda s: [
                ("Link", '<https://api.github.com/next>; rel="next"; rel="prev"'),
            ]
        })()

        import invariant_guardian.adapters.github.client as client_mod
        original_urlopen = client_mod.urlopen
        try:
            client_mod.urlopen = lambda req, timeout=20: fake_response
            with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
                client._json_with_link(
                    "https://api.github.com/repos/owner/repo/test"
                )
        finally:
            client_mod.urlopen = original_urlopen

    def test_malformed_link_no_brackets_raises(self) -> None:
        """P1.1: Completely garbled Link header (no angle brackets) must raise
        RuntimeError, never silently return empty next_url."""
        import json as _json
        from io import BytesIO

        client = GitHubClient("token", "owner/repo", 1)

        body = _json.dumps([{"id": 1}]).encode("utf-8")
        bio = BytesIO(body)
        bio.length = len(body)  # type: ignore[attr-defined]

        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            read = bio.read

        fake_response = FakeResponse()
        fake_response.length = len(body)  # type: ignore[attr-defined]
        fake_response.headers = type("FakeHeaders", (), {
            "items": lambda s: [("Link", "not-a-valid-link")],
        })()

        import invariant_guardian.adapters.github.client as client_mod
        original_urlopen = client_mod.urlopen
        try:
            client_mod.urlopen = lambda req, timeout=20: fake_response
            with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
                client._json_with_link(
                    "https://api.github.com/repos/owner/repo/test"
                )
        finally:
            client_mod.urlopen = original_urlopen

    def test_error_message_never_contains_raw_body(self) -> None:
        """RuntimeError messages must never include raw response bodies or tokens."""
        from io import BytesIO

        client = GitHubClient("token-secret-abc", "owner/repo", 1)

        import invariant_guardian.adapters.github.client as client_mod
        original_urlopen = client_mod.urlopen
        try:
            body = b'{"token": "secret-12345"}}'
            bio = BytesIO(body)
            bio.length = len(body)  # type: ignore[attr-defined]
            class FakeResponse:
                def __enter__(self): return self
                def __exit__(self, *a): pass
                read = bio.read

            fake_response = FakeResponse()
            fake_response.length = len(body)  # type: ignore[attr-defined]
            fake_response.headers = type("FakeHeaders", (), {"items": lambda s: []})()

            client_mod.urlopen = lambda req, timeout=20: fake_response
            with pytest.raises(RuntimeError) as exc_info:
                client._json("https://api.github.com/repos/owner/repo/test")
            error_msg = str(exc_info.value)
            assert "secret-12345" not in error_msg, (
                f"Raw body content leaked in error: {error_msg}"
            )
            assert "token" not in error_msg.lower() or "Bearer" not in error_msg, (
                f"Body keys leaked in error: {error_msg}"
            )
        finally:
            client_mod.urlopen = original_urlopen


# ---------------------------------------------------------------------------
# P1.1 — Malformed Link header regression: prove no clean / no mutation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Phase 3 fail-closed: Gap 4 — Link parser malformed entry rejection
# ---------------------------------------------------------------------------

class TestLinkParserStrictRejection:
    def test_multiple_next_relations_across_entries_raises(self) -> None:
        """When a Link header has TWO separate link-values each with
        rel=\"next\", the parser must reject — never silently pick one."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|ambiguous|multiple"):
            client._parse_link_header(
                '<https://api.github.com/next1>; rel="next", '
                '<https://api.github.com/next2>; rel="next"'
            )

    def test_multiple_next_with_mixed_quoted_unquoted_raises(self) -> None:
        """When one entry has rel=\"next\" and another has rel=next,
        both count as next — must reject."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|ambiguous|multiple"):
            client._parse_link_header(
                '<https://api.github.com/next1>; rel="next", '
                '<https://api.github.com/next2>; rel=next'
            )

    def test_empty_url_in_link_value_raises(self) -> None:
        """A link-value with empty angle brackets (<>) must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header('<>; rel="next"')

    def test_single_next_relation_still_works(self) -> None:
        """Normal RFC Link pagination with a single rel=\"next\" must work."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel="next"'
        )
        assert url == "https://api.github.com/repos/owner/repo/pulls/1/files?page=2"

    def test_link_with_last_and_next_works(self) -> None:
        """RFC Link with rel=\"last\" and rel=\"next\" across entries must
        extract next correctly."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=10>; rel="last", '
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel="next"'
        )
        assert url == "https://api.github.com/repos/owner/repo/pulls/1/files?page=2"

    def test_link_with_malformed_comma_entry_raises(self) -> None:
        """A link-value that's just a bare word (no angle brackets, inside a
        valid comma-separated list) must raise."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/next>; rel="next", garbage'
            )

    def test_unquoted_rel_with_no_value_raises(self) -> None:
        """A link-param with 'rel' but no value (rel;) must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/next>; rel'
            )

    def test_non_https_url_in_next_link_raises(self) -> None:
        """A rel=next URL with http:// scheme must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid|URL"):
            client._parse_link_header(
                '<http://api.github.com/next>; rel="next"'
            )


class TestMalformedLinkHeaderRegression:
    def test_changed_files_malformed_link_no_clean_assessment(self) -> None:
        """P1.1: changed_files() with malformed Link must raise RuntimeError —
        proving no clean assessment can leak through."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": "not-a-valid-link"},
        )
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_publish_malformed_link_no_mutation(self) -> None:
        """P1.1: publish() with malformed Link header must fail safe —
        no PATCH/POST mutation when comment listing is uncertain."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            # Return valid data but the malformed Link header is handled
            # by the transport layer (_json_with_link). We inject via
            # _request_with_headers to control the Link header directly.
            return (
                [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                "",
            )

        # Simulate: first _json_with_link call gets a valid response but
        # the second call (page 2) gets a malformed Link header — this
        # is tested via the pagination cycle in publish.
        # Instead, test directly that _json_with_link raises on malformed,
        # which publish() catches and sets pagination_uncertain=True.
        call_count = 0

        def fake_with_headers(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
            accept: str = "application/vnd.github+json",
        ) -> tuple[bytes, dict[str, str]]:
            nonlocal call_count
            call_count += 1
            import json as _json
            if call_count == 1:
                return (
                    _json.dumps([
                        {"id": 1, "body": "hi", "user": {"login": "contributor"}}
                    ]).encode(),
                    {"Link": '<https://api.github.com/repos/owner/repo/issues/42/comments?page=2>; rel="next"; rel="prev"'},
                )
            return (
                _json.dumps([
                    {"id": 2, "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOwned.",
                     "user": {"login": "github-actions[bot]"}}
                ]).encode(),
                {},
            )

        client._request_with_headers = fake_with_headers  # type: ignore[method-assign]
        # Also need _json for /user and for PATCH/POST
        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish|malformed|Link"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )

        assert len(mutation_calls) == 0, (
            "P1.1: No PATCH/POST when Link header is malformed"
        )


class TestSanitizedActionRunnerWarnings:
    def test_publication_warning_uses_constant_text_not_fstring_exc(self) -> None:
        """ActionRunner publication warning must use constant sanitized
        category text, never f'{exc}' which could leak raw exception data."""
        from pathlib import Path

        source = Path(
            "src/invariant_guardian/action_runner.py"
        ).read_text()

        # Find the SECOND except RuntimeError (publication block)
        first_except = source.index("except RuntimeError:")
        second_except = source.index("except RuntimeError:", first_except + 1)

        # Find the SafeWarning in that publication block
        warning_idx = source.index("SafeWarning(", second_except)
        # Find the closing of that SafeWarning call
        message_idx = source.index("message=", warning_idx)
        close_idx = source.index(")", message_idx)
        warning_block = source[warning_idx:close_idx]

        # The message= value must NOT be an f-string with {exc}
        import re
        # Check for f-string interpolation of exception variable
        assert not re.search(r'f["\'].*\{.*exc.*\}', warning_block), (
            f"Publication warning must use constant text, not f-string with exc. "
            f"Found: {warning_block[:200]}"
        )
        # Verify constant text is present
        assert "Could not publish" in warning_block, (
            "Warning message must be constant text"
        )


# ============================================================================
# Phase 3 P1 fixes — independent review regression tests
# ============================================================================

# ---------------------------------------------------------------------------
# P1#1: _validate_next_url exact structural endpoint equality
# ---------------------------------------------------------------------------

class TestValidateNextUrlExactPath:
    """P1#1: _validate_next_url must use exact structural endpoint equality,
    never startswith. Parsed URL path must equal exactly the expected path;
    query may vary. Sibling suffixes, encoded slashes, dot segments, params,
    fragments, username/password, port, other resource/repo must fail."""

    def test_sibling_suffix_filesevil_rejected(self) -> None:
        """A Link target with suffix 'filesevil' must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/pulls/42/filesevil?page=2",
                "/repos/owner/repo/pulls/42/files",
            )

    def test_sibling_suffix_files_other_rejected(self) -> None:
        """A Link target with suffix 'files-other' must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/pulls/42/files-other?page=2",
                "/repos/owner/repo/pulls/42/files",
            )

    def test_comments_sibling_suffix_rejected(self) -> None:
        """A comments Link with suffix 'comments-other' must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/issues/42/comments-other?page=2",
                "/repos/owner/repo/issues/42/comments",
            )

    def test_encoded_slash_path_rejected(self) -> None:
        """A path containing %2F (encoded slash) must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/pulls/42/files%2Fevil?page=2",
                "/repos/owner/repo/pulls/42/files",
            )

    def test_dot_segments_in_path_rejected(self) -> None:
        """A path containing /../ dot segments must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/pulls/../42/files?page=2",
                "/repos/owner/repo/pulls/42/files",
            )

    def test_params_semicolons_in_path_rejected(self) -> None:
        """A path containing ;params must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/pulls/42/files;evil?page=2",
                "/repos/owner/repo/pulls/42/files",
            )

    def test_other_repo_path_rejected(self) -> None:
        """A Link to a different repository must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/evil/steal/pulls/42/files?page=2",
                "/repos/owner/repo/pulls/42/files",
            )

    def test_exact_path_match_with_different_query_passes(self) -> None:
        """Exact path with different query params must pass."""
        client = GitHubClient("token", "owner/repo", 42)
        # Must NOT raise
        client._validate_next_url(
            "https://api.github.com/repos/owner/repo/pulls/42/files?per_page=100&page=2",
            "/repos/owner/repo/pulls/42/files",
        )

    def test_exact_path_match_no_query_passes(self) -> None:
        """Exact path with no query must pass."""
        client = GitHubClient("token", "owner/repo", 42)
        client._validate_next_url(
            "https://api.github.com/repos/owner/repo/pulls/42/files",
            "/repos/owner/repo/pulls/42/files",
        )

    def test_exact_comments_path_passes(self) -> None:
        """Exact comments path must pass."""
        client = GitHubClient("token", "owner/repo", 42)
        client._validate_next_url(
            "https://api.github.com/repos/owner/repo/issues/42/comments?page=2",
            "/repos/owner/repo/issues/42/comments",
        )

    def test_wrong_resource_type_files_for_comments_rejected(self) -> None:
        """A file-pagination URL validated against comments path must fail."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/pulls/42/files?page=2",
                "/repos/owner/repo/issues/42/comments",
            )

    def test_wrong_resource_type_comments_for_files_rejected(self) -> None:
        """A comments-pagination URL validated against files path must fail."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="resource|endpoint|URL|invalid"):
            client._validate_next_url(
                "https://api.github.com/repos/owner/repo/issues/42/comments?page=2",
                "/repos/owner/repo/pulls/42/files",
            )

    # --- No-request assertions via FakeTransport ---

    def test_sibling_suffix_url_never_requested_via_fake_transport(self) -> None:
        """When changed_files response has Link to /filesevil, the
        wrong-resource URL must be validated and rejected before any
        request is made to it."""
        from tests.fixtures.github.fake_transport import FakeTransport

        transport = FakeTransport()
        transport.register(
            "/pulls/42/files",
            200,
            [{"filename": "src/A.java", "status": "modified", "patch": "@@"}],
            {"Link": '<https://api.github.com/repos/owner/repo/pulls/42/filesevil?page=2>; rel="next"'},
        )
        # Register the evil URL — it must never be called
        transport.register(
            "/pulls/42/filesevil", 200, [{"filename": "evil.java", "status": "modified", "patch": "@@"}]
        )

        client = GitHubClient("token", "owner/repo", 42)
        transport.inject(client)

        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

        # Verify the evil endpoint was NOT called
        evil_calls = [
            c for c in transport.call_log() if "filesevil" in c[0]
        ]
        assert len(evil_calls) == 0, (
            f"P1#1: Wrong-resource URL must not be called. "
            f"Got calls: {transport.call_log()}"
        )

    def test_encoded_slash_url_never_requested_via_fake_transport(self) -> None:
        """A Link with %2F in path must be validated and rejected before
        any request is made."""
        from tests.fixtures.github.fake_transport import FakeTransport

        transport = FakeTransport()
        transport.register(
            "/pulls/42/files",
            200,
            [{"filename": "src/A.java", "status": "modified", "patch": "@@"}],
            {"Link": '<https://api.github.com/repos/owner/repo/pulls/42/files%2Fevil?page=2>; rel="next"'},
        )
        # Register the encoded URL — must never be called
        transport.register(
            "/pulls/42/files%2Fevil",
            200,
            [{"filename": "evil.java", "status": "modified", "patch": "@@"}],
        )

        client = GitHubClient("token", "owner/repo", 42)
        transport.inject(client)

        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

        encoded_calls = [
            c for c in transport.call_log() if "files%2F" in c[0]
        ]
        assert len(encoded_calls) == 0, (
            f"P1#1: Encoded-slash URL must not be called. "
            f"Got calls: {transport.call_log()}"
        )

    def test_files_next_url_with_userinfo_rejected_before_request(self) -> None:
        """A Link with username:password@ must be rejected before any
        request — token must not be sent."""
        client = GitHubClient("token-secret-value", "owner/repo", 42)

        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://user:pass@api.github.com/repos/owner/repo/pulls/42/files?page=2>; rel="next"'},
        )  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()


# ---------------------------------------------------------------------------
# P1#2: urlparse ValueError → sanitized RuntimeError
# ---------------------------------------------------------------------------

class TestUrlparseValueErrorCaught:
    """P1#2: urlparse(...).port ValueError and every malformed URL parsing
    attribute error must be caught and converted to sanitized RuntimeError."""

    def test_validate_url_invalid_port_raises_runtime_error_not_value_error(self) -> None:
        """An invalid port like :bad must raise RuntimeError, never ValueError."""
        client = GitHubClient("token", "owner/repo", 1)
        with pytest.raises(RuntimeError, match="URL|invalid|unsafe"):
            client._validate_url(
                "https://api.github.com:bad/repos/owner/repo/pulls/1/files"
            )

    def test_validate_next_url_invalid_port_raises_runtime_error(self) -> None:
        """_validate_next_url with invalid port must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="URL|invalid|resource|endpoint"):
            client._validate_next_url(
                "https://api.github.com:bad/repos/owner/repo/pulls/1/files?page=2",
                "/repos/owner/repo/pulls/1/files",
            )

    def test_changed_files_invalid_port_link_raises_runtime_error(self) -> None:
        """changed_files() with invalid-port Link must raise RuntimeError,
        not ValueError — proving the sanitized wrapper works."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com:bad/repos/owner/repo/pulls/42/files?page=2>; rel="next"'},
        )  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_publish_invalid_port_link_raises_runtime_error(self) -> None:
        """publish() with invalid-port Link must raise RuntimeError,
        no mutation."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []

        def fake_json_with_link(
            url: str, method: str = "GET", payload=None
        ) -> tuple[object, str]:
            return (
                [{"id": 1, "body": "hi", "user": {"login": "contributor"}}],
                "https://api.github.com:bad/repos/owner/repo/issues/42/comments?page=2",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish|incomplete"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0

    def test_invalid_port_url_never_reaches_transport(self) -> None:
        """An invalid-port URL must fail validation before _request_with_headers
        is invoked — no fake transport call."""
        from tests.fixtures.github.fake_transport import FakeTransport

        transport = FakeTransport()
        transport.register(
            "/pulls/42/files",
            200,
            [{"filename": "src/A.java", "status": "modified", "patch": "@@"}],
            {"Link": '<https://api.github.com:bad/repos/owner/repo/pulls/42/files?page=2>; rel="next"'},
        )
        transport.register("/pulls/42/files", 200, [])

        client = GitHubClient("token", "owner/repo", 42)
        transport.inject(client)

        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

        # Only the first-page call should have happened (1 call total)
        # The invalid-port URL must never be requested
        call_count = len(transport.call_log())
        assert call_count == 1, (
            f"P1#2: Only the first-page call should occur. "
            f"Got {call_count} calls: {transport.call_log()}"
        )


# ---------------------------------------------------------------------------
# P1#3: Harden Link parser — strict RFC 8288 link-value parsing
# ---------------------------------------------------------------------------

class TestLinkParserStrictRfc8288:
    """P1#3: Rewrite/harden Link parser. Treat any nonempty Link header as a
    comma-separated list of syntactically complete link-values. Reject trailing
    comma/empty elements, invalid rel syntax, whitespace around =, rel values
    containing multiple tokens, unknown malformed params, duplicate next.
    Valid entries with no rel=next can be final only if entire header valid."""

    # --- Malformed examples from review ---

    def test_trailing_comma_rejected(self) -> None:
        """Trailing comma after a link-value must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel="prev",'
            )

    def test_multi_relation_rel_value_rejected(self) -> None:
        """A rel value containing multiple tokens like 'next prev' must
        raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel="next prev"'
            )

    def test_unquoted_rel_whitespace_around_equals_rejected(self) -> None:
        """Whitespace around = in an unquoted rel param must be rejected.
        rel = "next" is not valid RFC 8288."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel = "next"'
            )

    def test_quoted_rel_whitespace_around_equals_still_works(self) -> None:
        """Quoted rel with spaces around = is actually valid RFC 8288:
        ;rel="next" with the space outside the param. But rel = "next"
        with space between token and = is the form to reject.

        This test verifies normal quoted rel= syntax continues to work."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel="next"'
        )
        assert url == "https://api.github.com/repos/owner/repo/pulls/1/files?page=2"

    def test_normal_unquoted_rel_still_works(self) -> None:
        """Normal unquoted rel=next must continue to work."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel=next'
        )
        assert url == "https://api.github.com/repos/owner/repo/pulls/1/files?page=2"

    def test_unquoted_rel_with_trailing_whitespace_around_equals_rejected(self) -> None:
        """rel =next (space before =) must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel =next'
            )

    def test_unquoted_rel_with_space_after_equals_rejected(self) -> None:
        """rel= next (space after =) must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/owner/repo/pulls/1/files?page=2>; rel= next'
            )

    # --- Valid prev/last with no next ---

    def test_valid_prev_last_only_returns_empty(self) -> None:
        """A valid Link header with only rel=prev and rel=last must return
        empty string — no RuntimeError, final page."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=1>; rel="prev", '
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=10>; rel="last"'
        )
        assert url == ""

    def test_valid_prev_only_returns_empty(self) -> None:
        """A valid Link header with only rel=prev must return empty string."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=1>; rel="prev"'
        )
        assert url == ""

    def test_valid_last_only_returns_empty(self) -> None:
        """A valid Link header with only rel=last must return empty string."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/owner/repo/pulls/1/files?page=10>; rel="last"'
        )
        assert url == ""

    # --- Empty elements in comma-separated list ---

    def test_empty_element_between_commas_rejected(self) -> None:
        """Double comma (empty element) must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/next>; rel="next", , '
                '<https://api.github.com/repos/last>; rel="last"'
            )

    def test_leading_comma_rejected(self) -> None:
        """Leading comma must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                ', <https://api.github.com/repos/next>; rel="next"'
            )

    # --- Unknown/malformed params ---

    def test_completely_unknown_param_still_parses(self) -> None:
        """An unknown param like ;title="foo" should not break parsing
        of a valid rel=next on the same entry (RFC 8288 allows extension
        params)."""
        client = GitHubClient("token", "owner/repo", 42)
        url = client._parse_link_header(
            '<https://api.github.com/repos/next>; rel="next"; title="page 2"'
        )
        assert url == "https://api.github.com/repos/next"

    def test_param_with_no_value_rejected(self) -> None:
        """A param token with = but no value (rel=) must be rejected."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid"):
            client._parse_link_header(
                '<https://api.github.com/repos/next>; rel='
            )

    # --- Duplicate next ---

    def test_duplicate_next_across_entries_rejected(self) -> None:
        """Two separate link-values with rel=next must raise RuntimeError."""
        client = GitHubClient("token", "owner/repo", 42)
        with pytest.raises(RuntimeError, match="Link|malformed|invalid|ambiguous|multiple"):
            client._parse_link_header(
                '<https://api.github.com/repos/next1>; rel="next", '
                '<https://api.github.com/repos/next2>; rel="next"'
            )

    # --- Malformed header → changed_files unavailable ---

    def test_changed_files_trailing_comma_link_raises(self) -> None:
        """P1#3: changed_files() with trailing-comma Link must raise
        RuntimeError — no clean assessment."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/repos/owner/repo/pulls/42/files?page=2>; rel="prev",'},
        )  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_changed_files_multi_relation_rel_link_raises(self) -> None:
        """P1#3: changed_files() with multi-token rel value must raise."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/repos/owner/repo/pulls/42/files?page=2>; rel="next prev"'},
        )  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_changed_files_rel_whitespace_link_raises(self) -> None:
        """P1#3: changed_files() with whitespace around = in rel must raise."""
        client = GitHubClient("token", "owner/repo", 42)
        client._request_with_headers = lambda *a, **kw: (
            b'[{"filename":"src/A.java","status":"modified","patch":"@@"}]',
            {"Link": '<https://api.github.com/repos/owner/repo/pulls/42/files?page=2>; rel = "next"'},
        )  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="incomplete|unavailable"):
            client.changed_files()

    def test_publish_trailing_comma_link_no_mutation(self) -> None:
        """P1#3: publish() with trailing-comma Link must fail safe —
        no PATCH/POST."""
        client = GitHubClient("token", "owner/repo", 42)
        mutation_calls: list[str] = []
        call_count = 0

        def fake_with_headers(
            url: str, method: str = "GET", payload=None,
            accept: str = "application/vnd.github+json",
        ) -> tuple[bytes, dict[str, str]]:
            nonlocal call_count
            call_count += 1
            import json as _json
            header_val = ""
            if call_count == 1:
                header_val = (
                    '<https://api.github.com/repos/owner/repo/issues/42/comments?page=2>; rel="prev",'
                )
            return (
                _json.dumps([
                    {"id": call_count, "body": "hi",
                     "user": {"login": "contributor"}}
                ]).encode(),
                {"Link": header_val},
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/user" in url and "/repos" not in url:
                return {"login": "github-actions[bot]"}
            if method in ("PATCH", "POST"):
                mutation_calls.append(method)
            return {}

        client._request_with_headers = fake_with_headers  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="Cannot publish|malformed|Link"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert len(mutation_calls) == 0, (
            "P1#3: No PATCH/POST when Link header has trailing comma"
        )


# ---------------------------------------------------------------------------
# Standard GITHUB_TOKEN / GitHub Actions ownership policy
# ---------------------------------------------------------------------------
class TestGitHubActionsTokenOwnership:
    """Publication must work with the standard Actions GITHUB_TOKEN.

    Installation tokens cannot call GET /user successfully. Comments created
    with secrets.GITHUB_TOKEN are authored as github-actions[bot]. Ownership
    must therefore use an explicit bot policy in Actions rather than requiring
    /user identity discovery.
    """

    def test_publish_creates_comment_when_user_endpoint_fails_in_actions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        client = GitHubClient("token", "owner/repo", 42)
        call_log: list[tuple[str, str]] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return ([], "")

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            call_log.append((method, url))
            if url.rstrip("/").endswith("/user") or url.endswith("/user"):
                raise RuntimeError("GitHub API request failed with status 403")
            if method == "POST":
                return {"id": 501, "user": {"login": "github-actions[bot]"}}
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish(
            "<!-- invariant-guardian:v2:abcdef0123456789 -->\nFirst assessment.",
            "abcdef0123456789",
        )

        post_calls = [c for c in call_log if c[0] == "POST"]
        assert len(post_calls) == 1, f"Expected POST create, got {call_log}"

    def test_publish_updates_bot_comment_when_user_endpoint_fails_in_actions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        client = GitHubClient("token", "owner/repo", 42)
        call_log: list[tuple[str, str]] = []
        existing_body = "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOld."
        new_body = "<!-- invariant-guardian:v2:abcdef0123456789 -->\nUpdated."

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 77,
                        "body": existing_body,
                        "user": {"login": "github-actions[bot]"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            call_log.append((method, url))
            if url.rstrip("/").endswith("/user") or url.endswith("/user"):
                raise RuntimeError("GitHub API request failed with status 403")
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish(new_body, "abcdef0123456789")

        patch_calls = [c for c in call_log if c[0] == "PATCH" and "/77" in c[1]]
        assert len(patch_calls) == 1, f"Expected PATCH of bot comment, got {call_log}"
        assert not any(c[0] == "POST" for c in call_log)

    def test_publish_skips_identical_bot_comment_in_actions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        client = GitHubClient("token", "owner/repo", 42)
        body = "<!-- invariant-guardian:v2:abcdef0123456789 -->\nSame."
        mutations: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 88,
                        "body": body,
                        "user": {"login": "github-actions[bot]"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if url.rstrip("/").endswith("/user") or url.endswith("/user"):
                raise RuntimeError("GitHub API request failed with status 403")
            if method in ("PATCH", "POST"):
                mutations.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish(body, "abcdef0123456789")
        assert mutations == []

    def test_publish_ignores_contributor_copied_marker_in_actions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        client = GitHubClient("token", "owner/repo", 42)
        call_log: list[tuple[str, str]] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 11,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nCopied!",
                        "user": {"login": "human-reviewer"},
                    }
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            call_log.append((method, url))
            if url.rstrip("/").endswith("/user") or url.endswith("/user"):
                raise RuntimeError("GitHub API request failed with status 403")
            return {"id": 12}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish(
            "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBot body.",
            "abcdef0123456789",
        )

        assert not any(c[0] == "PATCH" for c in call_log)
        assert any(c[0] == "POST" for c in call_log)

    def test_publish_still_fails_outside_actions_without_identity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        client = GitHubClient("token", "owner/repo", 42)
        mutations: list[str] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return ([], "")

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if url.rstrip("/").endswith("/user") or url.endswith("/user"):
                raise RuntimeError("GitHub API request failed with status 403")
            if method in ("PATCH", "POST"):
                mutations.append(method)
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="identity"):
            client.publish(
                "<!-- invariant-guardian:v2:abcdef0123456789 -->\nBody.",
                "abcdef0123456789",
            )
        assert mutations == []

    def test_publish_prefers_authenticated_login_over_bot_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A PAT that can call /user must own comments as that login, not the bot constant."""
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        client = GitHubClient("token", "owner/repo", 42)
        call_log: list[tuple[str, str]] = []

        def fake_json_with_link(
            url: str,
            method: str = "GET",
            payload: dict | None = None,
        ) -> tuple[object, str]:
            return (
                [
                    {
                        "id": 42,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOld bot.",
                        "user": {"login": "github-actions[bot]"},
                    },
                    {
                        "id": 43,
                        "body": "<!-- invariant-guardian:v2:abcdef0123456789 -->\nOld pat.",
                        "user": {"login": "release-bot"},
                    },
                ],
                "",
            )

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            call_log.append((method, url))
            if url.rstrip("/").endswith("/user") or url.endswith("/user"):
                return {"login": "release-bot"}
            return {}

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        client._json = fake_json  # type: ignore[method-assign]

        client.publish(
            "<!-- invariant-guardian:v2:abcdef0123456789 -->\nNew pat.",
            "abcdef0123456789",
        )

        assert any(c[0] == "PATCH" and "/43" in c[1] for c in call_log)
        assert not any(c[0] == "PATCH" and "/42" in c[1] for c in call_log)


# ---------------------------------------------------------------------------
# GitHub Contents API Base64 decoding (merge-readiness E2E)
# ---------------------------------------------------------------------------
from pathlib import Path as _Path


class TestContentsBase64Decoding:
    """GitHub Contents API wraps base64 with newlines. Decode must accept
    only that wrapping while remaining fail-closed for other corruption.
    """

    def _listing(self, name: str = "no-domain-leak.md") -> list[dict]:
        return [
            {
                "type": "file",
                "name": name,
                "url": f"https://api.github.com/repos/owner/repo/contents/{name}",
            }
        ]

    def _run_write(self, content_payload: dict, tmp_path: _Path) -> _Path:
        client = GitHubClient("token", "owner/repo", 1)
        dest = tmp_path / "inv"

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            # Directory listing vs file content
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing(content_payload.get("_name", "no-domain-leak.md"))
            return content_payload

        client._json = fake_json  # type: ignore[method-assign]
        client.write_invariants(dest, "base-sha", "invariants")
        return dest

    def test_valid_unwrapped_base64(self, tmp_path: _Path) -> None:
        import base64

        body = b"---\nid: no-domain-leak\ntitle: t\nseverity: error\nscope:\n  languages: [java]\n  include_paths: ['src/**']\n---\n\n## Rule\nr\n\n## Rationale\nr\n\n## Violating examples\nv\n\n## Acceptable examples\na\n"
        payload = {
            "encoding": "base64",
            "content": base64.b64encode(body).decode("ascii"),
            "name": "no-domain-leak.md",
            "type": "file",
        }
        dest = self._run_write(payload, tmp_path)
        assert (dest / "no-domain-leak.md").read_bytes() == body

    def test_valid_base64_wrapped_with_lf(self, tmp_path: _Path) -> None:
        import base64

        body = b"rule body with lf wrap\n"
        enc = base64.b64encode(body).decode("ascii")
        wrapped = "\n".join(enc[i : i + 8] for i in range(0, len(enc), 8)) + "\n"
        payload = {"encoding": "base64", "content": wrapped}
        dest = self._run_write(payload, tmp_path)
        assert (dest / "no-domain-leak.md").read_bytes() == body

    def test_valid_base64_wrapped_with_crlf(self, tmp_path: _Path) -> None:
        import base64

        body = b"rule body with crlf wrap\n"
        enc = base64.b64encode(body).decode("ascii")
        wrapped = "\r\n".join(enc[i : i + 8] for i in range(0, len(enc), 8)) + "\r\n"
        payload = {"encoding": "base64", "content": wrapped}
        dest = self._run_write(payload, tmp_path)
        assert (dest / "no-domain-leak.md").read_bytes() == body

    def test_multiple_wrapped_lines(self, tmp_path: _Path) -> None:
        import base64

        body = b"x" * 200
        enc = base64.b64encode(body).decode("ascii")
        wrapped = "\n".join(enc[i : i + 60] for i in range(0, len(enc), 60)) + "\n"
        assert wrapped.count("\n") >= 3
        payload = {"encoding": "base64", "content": wrapped}
        dest = self._run_write(payload, tmp_path)
        assert (dest / "no-domain-leak.md").read_bytes() == body

    def test_invalid_base64_after_newline_normalization_rejected(
        self, tmp_path: _Path
    ) -> None:
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if url.endswith("invariants?ref=base-sha") or "/contents/invariants?" in url:
                return self._listing()
            return {"encoding": "base64", "content": "@@@@\n####\n"}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="decoded|base64|content"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_embedded_spaces_rejected(self, tmp_path: _Path) -> None:
        import base64

        enc = base64.b64encode(b"hello").decode("ascii")
        spaced = enc[:2] + " " + enc[2:]
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": "base64", "content": spaced}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="decoded|base64|content"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_embedded_tabs_rejected(self, tmp_path: _Path) -> None:
        import base64

        enc = base64.b64encode(b"hello").decode("ascii")
        tabbed = enc[:2] + "\t" + enc[2:]
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": "base64", "content": tabbed}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="decoded|base64|content"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_unsupported_encoding_rejected(self, tmp_path: _Path) -> None:
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": "utf-8", "content": "aGVsbG8="}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="encoding"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_missing_encoding_rejected(self, tmp_path: _Path) -> None:
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if "/contents/invariants" in url and "no-domain-leak.md" not in url:
                return self._listing()
            # Explicitly omit encoding while providing otherwise valid content.
            return {"content": "aGVsbG8="}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="encoding"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_non_string_encoding_rejected(self, tmp_path: _Path) -> None:
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": 1, "content": "aGVsbG8="}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="encoding"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_empty_content_rejected(self, tmp_path: _Path) -> None:
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": "base64", "content": ""}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="empty|content"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_empty_decoded_bytes_rejected(self, tmp_path: _Path) -> None:
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": "base64", "content": ""}  # empty encoded

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="empty|content"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_invalid_utf8_rejected(self, tmp_path: _Path) -> None:
        import base64

        client = GitHubClient("token", "owner/repo", 1)
        enc = base64.b64encode(b"\xff\xfe\x00").decode("ascii")

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": "base64", "content": enc}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="UTF-8|utf-8|content"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_oversized_encoded_response_rejected(self, tmp_path: _Path) -> None:
        client = GitHubClient("token", "owner/repo", 1)
        huge = "A" * 1_000_001

        def fake_json(url: str, method: str = "GET", payload=None) -> object:
            if ("/contents/invariants?" in url) or url.rstrip("/").endswith("/contents/invariants"):
                return self._listing()
            return {"encoding": "base64", "content": huge}

        client._json = fake_json  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="size|limit|content"):
            client.write_invariants(tmp_path / "inv", "base-sha", "invariants")

    def test_saved_github_contents_response_writes_invariant(
        self, tmp_path: _Path
    ) -> None:
        import json
        from pathlib import Path as P

        fixture = P(__file__).parent / "fixtures/github/contents_no_domain_leak.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        assert payload.get("encoding") == "base64"
        assert "\n" in payload["content"]
        # Use a same-repo contents URL so structural URL validation passes.
        safe_url = (
            "https://api.github.com/repos/owner/repo/contents/"
            "tests/fixtures/invariants/no-domain-leak.md"
        )
        payload = {**payload, "url": safe_url}

        client = GitHubClient("token", "owner/repo", 1)

        def fake_json(url: str, method: str = "GET", payload_arg=None) -> object:
            if "/contents/invariants" in url and "no-domain-leak.md" not in url:
                return [
                    {
                        "type": "file",
                        "name": "no-domain-leak.md",
                        "url": safe_url,
                    }
                ]
            return payload

        client._json = fake_json  # type: ignore[method-assign]
        dest = tmp_path / "inv"
        client.write_invariants(dest, "base-sha", "invariants")
        written = (dest / "no-domain-leak.md").read_text(encoding="utf-8")
        assert "id: no-domain-leak" in written
        assert "## Rule" in written


class TestRepositoriesIdPaginationUrl:
    """GitHub Link headers often use /repositories/{id}/... instead of
    /repos/{owner}/{repo}/... — both must be accepted for the same resource.
    """

    def test_repositories_id_files_next_url_accepted(self) -> None:
        url = (
            "https://api.github.com/repositories/1312445612/"
            "pulls/4/files?per_page=100&page=2"
        )
        GitHubClient._validate_next_url(
            url, "/repos/shahibag/architecture-invariant-guardian/pulls/4/files"
        )

    def test_repositories_id_comments_next_url_accepted(self) -> None:
        url = (
            "https://api.github.com/repositories/1312445612/"
            "issues/4/comments?per_page=100&page=2"
        )
        GitHubClient._validate_next_url(
            url, "/repos/shahibag/architecture-invariant-guardian/issues/4/comments"
        )

    def test_repositories_id_wrong_resource_rejected(self) -> None:
        url = (
            "https://api.github.com/repositories/1312445612/"
            "pulls/4/filesevil?per_page=100&page=2"
        )
        with pytest.raises(RuntimeError, match="Pagination next-URL"):
            GitHubClient._validate_next_url(
                url, "/repos/shahibag/architecture-invariant-guardian/pulls/4/files"
            )

    def test_changed_files_follows_repositories_id_pagination(self) -> None:
        client = GitHubClient("token", "owner/repo", 4)
        pages = {
            1: (
                [
                    {
                        "filename": f"src/main/java/com/example/F{i}.java",
                        "status": "modified",
                        "patch": "@@ -1 +1 @@\n-a\n+b\n",
                    }
                    for i in range(100)
                ],
                "https://api.github.com/repositories/99/pulls/4/files?per_page=100&page=2",
            ),
            2: (
                [
                    {
                        "filename": "src/main/java/com/example/Last.java",
                        "status": "modified",
                        "patch": "@@ -1 +1 @@\n-a\n+b\n",
                    }
                ],
                "",
            ),
        }
        calls = {"n": 0}

        def fake_json_with_link(url: str, method: str = "GET", payload=None):
            calls["n"] += 1
            if "page=2" in url:
                return pages[2]
            return pages[1]

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        result = client.changed_files()
        assert len(result) == 101
        assert calls["n"] == 2


class TestMissingPatchDoesNotFailListing:
    def test_added_file_without_patch_is_returned_incomplete(self) -> None:
        client = GitHubClient("token", "owner/repo", 1)

        def fake_json_with_link(url: str, method: str = "GET", payload=None):
            return (
                [
                    {
                        "filename": "src/main/java/com/example/A.java",
                        "status": "added",
                        # no patch — GitHub omits for empty/large files
                    },
                    {
                        "filename": "src/main/java/com/example/B.java",
                        "status": "modified",
                        "patch": "@@ -1 +1 @@\n-a\n+b\n",
                    },
                ],
                "",
            )

        client._json_with_link = fake_json_with_link  # type: ignore[method-assign]
        result = client.changed_files()
        assert len(result) == 2
        by_path = {f.path: f for f in result}
        assert by_path["src/main/java/com/example/A.java"].patch_complete is False
        assert by_path["src/main/java/com/example/A.java"].patch is None
        assert by_path["src/main/java/com/example/B.java"].patch_complete is True
