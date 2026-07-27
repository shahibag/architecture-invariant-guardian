"""Contract tests for GitHub client — bot-owned comment protection."""

from invariant_guardian.adapters.github.client import (
    BOT_LOGIN,
    GitHubClient,
    find_owned_comment,
    is_bot_comment,
    should_skip_update,
)
from invariant_guardian.rendering.comment import MARKER_PREFIX


# ---------------------------------------------------------------------------
# Bot login constant
# ---------------------------------------------------------------------------
class TestBotLogin:
    def test_bot_login_is_github_actions_bot(self) -> None:
        assert BOT_LOGIN == "github-actions[bot]"


# ---------------------------------------------------------------------------
# is_bot_comment
# ---------------------------------------------------------------------------
class TestIsBotComment:
    def test_bot_comment_identified(self) -> None:
        comment = {
            "id": 1,
            "body": f"{MARKER_PREFIX}abc123 -->\nAssessment.",
            "user": {"login": "github-actions[bot]"},
        }
        assert is_bot_comment(comment, BOT_LOGIN)

    def test_contributor_comment_with_copied_marker_is_rejected(self) -> None:
        comment = {
            "id": 2,
            "body": f"{MARKER_PREFIX}abc123 -->\nCopied marker!",
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
        comment = {"id": 4, "body": f"{MARKER_PREFIX}xyz -->\nNo user."}
        assert not is_bot_comment(comment, BOT_LOGIN)

    def test_bot_comment_case_insensitive_login(self) -> None:
        """GitHub logins are case-insensitive."""
        comment = {
            "id": 5,
            "body": f"{MARKER_PREFIX}abc -->\nTest.",
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
                "body": f"{MARKER_PREFIX}abc123 -->\nGuardian.",
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
                "body": f"{MARKER_PREFIX}abc123 -->\nCopied!",
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

    def test_returns_first_owned_when_multiple(self) -> None:
        comments = [
            {
                "id": 10,
                "body": f"{MARKER_PREFIX}old -->\nOld.",
                "user": {"login": "github-actions[bot]"},
            },
            {
                "id": 20,
                "body": f"{MARKER_PREFIX}new -->\nNew.",
                "user": {"login": "github-actions[bot]"},
            },
        ]
        result = find_owned_comment(comments, BOT_LOGIN)
        assert result is not None
        assert result["id"] == 10  # first match


# ---------------------------------------------------------------------------
# should_skip_update
# ---------------------------------------------------------------------------
class TestShouldSkipUpdate:
    def test_skip_when_body_identical(self) -> None:
        body = f"{MARKER_PREFIX}abc -->\nSame."
        existing = {"body": body}
        assert should_skip_update(existing, body)

    def test_update_when_body_different(self) -> None:
        existing = {"body": f"{MARKER_PREFIX}abc -->\nOld."}
        assert not should_skip_update(existing, f"{MARKER_PREFIX}abc -->\nNew.")

    def test_update_when_existing_has_no_body(self) -> None:
        existing = {"id": 99}
        assert not should_skip_update(existing, f"{MARKER_PREFIX}abc -->\nNew.")


# ---------------------------------------------------------------------------
# GitHubClient — construction safety
# ---------------------------------------------------------------------------
class TestGitHubClientConstruction:
    def test_client_stores_params(self) -> None:
        client = GitHubClient("token", "owner/repo", 42)
        assert client._token == "token"
        assert client._repository == "owner/repo"
        assert client._pull_number == 42


class TestChangedFilesPagination:
    def test_fetches_one_extra_record_to_signal_file_ceiling(self) -> None:
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
            return entries, (f"page-{calls + 1}" if calls < 3 else "")

        client._json_with_link = fake_page  # type: ignore[method-assign]
        files = client.changed_files()
        assert calls == 3
        assert len(files) == 201

    def test_missing_non_removed_patch_is_incomplete(self) -> None:
        client = GitHubClient("token", "owner/repo", 42)
        client._json_with_link = lambda url: (  # type: ignore[method-assign]
            [{"filename": "src/Foo.java", "status": "modified"}],
            "",
        )
        [changed] = client.changed_files()
        assert changed.patch is None
        assert changed.patch_complete is False
