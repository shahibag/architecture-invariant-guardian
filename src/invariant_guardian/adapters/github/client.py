"""Minimal GitHub REST client — bot-owned comment protection, no PR checkout."""

from __future__ import annotations

import base64
import binascii
import json
import re
import time
from pathlib import Path
from typing import IO, Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{16}$")


def _is_safe_repo_path(path: str) -> bool:
    """Return True when *path* is a safe, nonempty repository-relative
    POSIX path with no NUL, no leading ``/``, no ``.`` or ``..``
    components, and no backslash separators."""
    if not path:
        return False
    if "\x00" in path:
        return False
    if path.startswith("/"):
        return False
    if "\\" in path:
        return False
    # Reject . or .. components
    parts = path.split("/")
    for part in parts:
        if part in (".", ".."):
            return False
        if not part:
            return False  # empty component (// or trailing /)
    return True

# RFC 8288 link-value pattern: <url> *(; param=value)
# Used to validate Link headers — rejects ambiguous rel syntax.
# Phase 3 P1#3: tightened — no whitespace around = in params.
_LINK_VALUE_RE = re.compile(
    r"<([^>]+)>\s*((?:;\s*\w+=(?:\"[^\"]*\"|\w+)\s*)*)"
)
# Pattern to count rel= occurrences — used to reject ambiguous entries
_REL_ASSIGN_RE = re.compile(r"\brel=")

from invariant_guardian.context import (
    MAX_CHANGED_FILE_BYTES,
    MAX_CHANGED_FILE_PAGES,
    MAX_CHANGED_FILES,
    MAX_COMMENT_BYTES,
    MAX_COMMENT_PAGES,
    MAX_COMMENTS,
    MAX_HTTP_RETRIES,
    MAX_RESPONSE_BYTES,
    MAX_RETRY_DELAY,
)
from invariant_guardian.domain.models import ChangedFile
from invariant_guardian.rendering.comment import MARKER_RE

BOT_LOGIN = "github-actions[bot]"


def _bounded_read(response: IO[bytes]) -> bytes:
    """Read *response* bounded by MAX_RESPONSE_BYTES+1.

    Never trusts Content-Length — the header can lie or be malformed.
    Always reads incrementally up to the hard cap (MAX_RESPONSE_BYTES+1).
    Content-Length is advisory only; the actual bytes read determine
    whether the response is oversized.

    Raises RuntimeError (sanitised, no token/body) when the actual
    response body exceeds MAX_RESPONSE_BYTES.
    """
    limit = MAX_RESPONSE_BYTES + 1
    chunk_size = 8192
    chunks: list[bytes] = []
    total = 0
    while total < limit:
        to_read = min(chunk_size, limit - total)
        chunk = response.read(to_read)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)

    if total > MAX_RESPONSE_BYTES:
        raise RuntimeError("Response size exceeds limit.")
    return b"".join(chunks)


def is_bot_comment(comment: dict[str, Any], bot_login: str) -> bool:
    """Return True when *comment* was authored by the bot *and* the
    first line is an exact v2 Guardian marker (16 hex chars).

    Substrings, copied/quoted markers, v1/v3 syntax, markers on other
    lines, and wrong fingerprint lengths are all rejected.
    """
    user = comment.get("user", {})
    if not isinstance(user, dict):
        return False
    login = user.get("login", "")
    if not isinstance(login, str):
        return False
    if login.lower() != bot_login.lower():
        return False
    body = comment.get("body", "")
    if not isinstance(body, str):
        return False
    # Strict first-line anchored match only
    first_line = body.split("\n")[0]
    return MARKER_RE.match(first_line) is not None


def find_owned_comment(
    comments: list[dict[str, Any]], bot_login: str
) -> dict[str, Any] | None:
    """Return the bot-owned Guardian comment, or None.

    Contributor-authored comments with copied markers are never returned.
    When more than one distinct bot-owned Guardian comment exists the
    function raises RuntimeError — the caller must fail safe rather than
    choose or silently create duplicates.
    """
    owned: list[dict[str, Any]] = []
    for comment in comments:
        if isinstance(comment, dict) and is_bot_comment(comment, bot_login):
            owned.append(comment)
    if len(owned) > 1:
        raise RuntimeError(
            "Multiple bot-owned Guardian comments exist — publication is "
            "ambiguous and cannot proceed safely."
        )
    if len(owned) == 1:
        return owned[0]
    # Zero owned → None
    return None


def should_skip_update(existing: dict[str, Any], new_body: str) -> bool:
    """Return True when the comment body is already identical."""
    return existing.get("body") == new_body


class GitHubClient:
    """Minimal GitHub REST client. It never checks out or executes PR code."""

    def __init__(self, token: str, repository: str, pull_number: int) -> None:
        self._token = token
        self._repository = repository
        self._pull_number = pull_number
        self._base = f"https://api.github.com/repos/{repository}"
        self._source_roots_cache: dict[str, list[str] | None] = {}
        self._cached_login: str | None = None

    def pull_diff(self) -> str:
        return self._request(
            f"{self._base}/pulls/{self._pull_number}",
            accept="application/vnd.github.v3.diff",
        ).decode("utf-8")

    def list_source_roots(self, ref: str) -> list[str] | None:
        """Return known Java source-root directories at *ref* (exact SHA).

        Uses the Git Trees API to discover directories that contain
        ``.java`` files.  Entries and response bytes are bounded —
        truncated results return a partial list, never a fabricated one.

        Returns ``None`` when the API is unavailable or returns
        non-directory entries.  This is a saved-fake-responses-only
        implementation for P1 finding 3 (cross-module imports).
        """
        if ref in self._source_roots_cache:
            return self._source_roots_cache[ref]

        try:
            tree = self._json(
                f"{self._base}/git/trees/{ref}?recursive=1",
            )
        except RuntimeError:
            self._source_roots_cache[ref] = None
            return None

        if not isinstance(tree, dict):
            self._source_roots_cache[ref] = None
            return None
        if tree.get("truncated") is True:
            self._source_roots_cache[ref] = None
            return None
        entries = tree.get("tree")
        if not isinstance(entries, list):
            self._source_roots_cache[ref] = None
            return None

        # Collect directories containing .java files (bounded)
        roots: set[str] = set()
        max_entries = 500  # hard cap — never unbounded
        if len(entries) > max_entries:
            self._source_roots_cache[ref] = None
            return None
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "blob":
                continue
            path = entry.get("path", "")
            if not isinstance(path, str) or not path.endswith(".java"):
                continue
            # Derive source root from the path
            parts = path.split("/")
            for index in range(max(0, len(parts) - 2)):
                segment = parts[index : index + 3]
                if segment in (["src", "main", "java"], ["src", "test", "java"]):
                    roots.add("/".join(parts[: index + 3]))
                    break
            else:
                # Use the parent directory as a potential root
                if len(parts) > 1:
                    roots.add("/".join(parts[:-1]))
        if len(roots) > 20:
            self._source_roots_cache[ref] = None
            return None
        result = sorted(roots) if roots else None
        self._source_roots_cache[ref] = result
        return result

    def read_file_at_ref(self, path: str, ref: str) -> bytes | None:
        """Fetch the raw content of *path* at *ref* (exact SHA/ref).

        Uses the GitHub Contents API.  Returns ``None`` when the file is
        missing, is a directory, or exceeds a reasonable size threshold.
        The caller must still apply ``read_source_safely`` for binary
        rejection and strict UTF-8 decoding.
        """
        # Validate path — must be repository-relative, no traversal
        if not path or "\x00" in path or path.startswith("/"):
            return None
        if ".." in path.split("/"):
            return None

        try:
            raw = self._request(
                f"{self._base}/contents/{path}?ref={ref}",
                accept="application/vnd.github.raw",
            )
        except RuntimeError:
            # GitHub returns 404 for missing files, 403 for large/binary
            return None

        if raw is None or len(raw) == 0:
            return None
        return raw

    def changed_files(self) -> list[ChangedFile]:
        """Fetch the PR file listing from the GitHub REST API, paginating
        through all pages up to the Phase 3 bounded ceilings.

        Each file includes its per-file patch (bounded by GitHub).  No
        checkout or execution of PR code is performed.

        Raises RuntimeError (sanitised, no raw response data) when the
        listing is incomplete or uncertain — non-list pages, invalid
        entries, API/JSON failures, off-origin next links, URL cycles,
        cap exhaustion, or missing patches on added/modified/renamed
        files.  Removed files may omit their patch without triggering
        the error.

        The caller (ActionRunner) must catch this and emit
        ``assessment_incomplete`` with a sanitised warning.
        """
        result: list[ChangedFile] = []
        url = f"{self._base}/pulls/{self._pull_number}/files?per_page=100"
        pages_fetched = 0
        total_bytes = 0
        seen_urls: set[str] = set()
        uncertain = False

        while url and pages_fetched < MAX_CHANGED_FILE_PAGES:
            # Cycle detection — repeated URL
            if url in seen_urls:
                uncertain = True
                break
            seen_urls.add(url)
            pages_fetched += 1

            try:
                raw, next_url = self._json_with_link(url)
            except RuntimeError:
                uncertain = True
                break

            if not isinstance(raw, list):
                uncertain = True
                break

            for entry in raw:
                if not isinstance(entry, dict):
                    uncertain = True
                    continue
                filename = entry.get("filename", "")
                if not isinstance(filename, str) or not filename:
                    uncertain = True
                    continue
                # Phase 3 fail-closed: validate filename safety
                if not _is_safe_repo_path(filename):
                    uncertain = True
                    continue
                # Phase 3 fail-closed: missing status key → unavailable,
                # never silently default to "modified"
                status = entry.get("status")
                if not isinstance(status, str) or status not in (
                    "added", "modified", "removed", "renamed"
                ):
                    uncertain = True
                    continue
                patch = entry.get("patch")
                patch_str = patch if isinstance(patch, str) else None
                # Missing patch on added/modified/renamed → uncertainty
                # Removed files may omit patch; non-string patch is unavailable
                if patch_str is None and status != "removed":
                    uncertain = True
                patch_complete = not (
                    patch_str is None and status != "removed"
                )
                previous = entry.get("previous_filename")
                previous_str = previous if isinstance(previous, str) else None
                # Phase 3 fail-closed: renamed files require safe previous_filename
                if status == "renamed" and (
                    not previous_str or not _is_safe_repo_path(previous_str)
                ):
                    uncertain = True
                    continue
                result.append(
                    ChangedFile(
                        path=filename,
                        status=status,  # type: ignore[arg-type]
                        patch=patch_str,
                        patch_complete=patch_complete,
                        previous_filename=previous_str,
                    )
                )
                # File cap exhaustion — one extra record triggers uncertainty
                if len(result) > MAX_CHANGED_FILES:
                    uncertain = True
                    break

            # When the for-loop broke due to file-cap exhaustion, also
            # break the while loop — no point in fetching more pages.
            if len(result) > MAX_CHANGED_FILES:
                break

            # Estimate JSON bytes per page
            total_bytes += len(json.dumps(raw).encode("utf-8"))
            if total_bytes > MAX_CHANGED_FILE_BYTES:
                uncertain = True
                break

            # Page cap exhaustion
            if pages_fetched >= MAX_CHANGED_FILE_PAGES and next_url:
                uncertain = True
                break

            # Phase 3 fail-closed: structural URL validation for pagination
            if next_url:
                expected_prefix = (
                    f"/repos/{self._repository}/pulls/{self._pull_number}/files"
                )
                try:
                    self._validate_next_url(next_url, expected_prefix)
                except RuntimeError:
                    uncertain = True
                    break
            url = next_url

        if uncertain:
            raise RuntimeError(
                "Changed file listing is incomplete or unavailable"
            )
        return result

    def write_invariants(self, destination: Path, ref: str, directory: str) -> None:
        """Fetch invariant Markdown files from the repository.

        Validates every entry and URL — path traversal, off-origin, and
        malformed responses all raise sanitised RuntimeError.
        """
        listing = self._json(
            f"{self._base}/contents/{directory.lstrip('/')}?ref={ref}"
        )
        if not isinstance(listing, list):
            raise RuntimeError(  # noqa: TRY004 — sanitised, never TypeError
                "Invariant directory listing is not a valid directory"
            )
        destination.mkdir(parents=True, exist_ok=True)
        for entry in listing:
            if not isinstance(entry, dict):
                raise RuntimeError(  # noqa: TRY004 — sanitised, never TypeError
                    "Invariant directory listing contains invalid entry"
                )
            # Phase 3 fail-closed: every entry must be well-formed
            name = entry.get("name", "")
            if not isinstance(name, str) or not name:
                raise RuntimeError(
                    "Invariant directory listing contains entry with "
                    "missing or invalid name"
                )
            # Reject path traversal in entry names
            if "/" in name or "\\" in name or name.startswith("."):
                raise RuntimeError(
                    "Invariant file name is not a safe basename"
                )
            entry_type = entry.get("type", "")
            if not isinstance(entry_type, str) or not entry_type:
                raise RuntimeError(
                    "Invariant directory listing contains entry with "
                    "missing or invalid type"
                )
            # Only regular files may be processed; non-md files are
            # safely ignored iff shape is well-formed
            if entry_type != "file" or not name.endswith(".md"):
                continue
            entry_url = entry.get("url", "")
            if not isinstance(entry_url, str) or not entry_url:
                raise RuntimeError(
                    "Invariant entry has missing or invalid URL"
                )
            # Phase 3 fail-closed: structural URL validation via urlparse
            try:
                self._validate_url(entry_url)
            except RuntimeError:
                raise RuntimeError(
                    "Invariant entry URL is outside the repository"
                )
            parsed = urlparse(entry_url)
            expected_contents_prefix = (
                f"/repos/{self._repository}/contents/"
            )
            if not parsed.path.startswith(expected_contents_prefix):
                raise RuntimeError(
                    "Invariant entry URL is outside the repository"
                )
            contents = self._json(entry_url)
            if not isinstance(contents, dict):
                raise RuntimeError(  # noqa: TRY004 — sanitised, never TypeError
                    "Invariant content response is malformed"
                )
            encoded = contents.get("content", "")
            if not isinstance(encoded, str):
                raise RuntimeError(  # noqa: TRY004 — sanitised, never TypeError
                    "Invariant file content is not valid base64"
                )
            if len(encoded) > 1_000_000:  # 1 MiB cap for base64 content
                raise RuntimeError(
                    "Invariant file content exceeds size limit"
                )
            # Phase 3 fail-closed: validate base64 content
            if not encoded:
                raise RuntimeError(
                    "Invariant file content is empty"
                )
            try:
                ascii_encoded = encoded.encode("ascii")
            except UnicodeEncodeError:
                raise RuntimeError(
                    "Invariant file content contains non-ASCII characters"
                )
            try:
                decoded_bytes = base64.b64decode(ascii_encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                # binascii.Error: invalid base64 characters or padding
                # ValueError: other decode failures — sanitise all
                raise RuntimeError(
                    "Invariant file content could not be decoded"
                ) from exc
            # Reject empty decoded content
            if not decoded_bytes:
                raise RuntimeError(
                    "Invariant file content decoded to empty bytes"
                )
            # Reject non-UTF-8 (binary) decoded content
            try:
                decoded_text = decoded_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raise RuntimeError(
                    "Invariant file content is not valid UTF-8"
                )
            if not decoded_text.strip():
                raise RuntimeError(
                    "Invariant file content is empty after decoding"
                )
            (destination / name).write_bytes(decoded_bytes)

    def authenticated_login(self) -> str | None:
        """Retrieve and cache the authenticated bot identity from /user.

        Returns the login string, or ``None`` when the identity cannot be
        confirmed (non-dict response, missing login key, API error).
        The result is cached so the user endpoint is called at most once.
        """
        if self._cached_login is not None:
            return self._cached_login
        try:
            user = self._json("https://api.github.com/user")
        except RuntimeError:
            self._cached_login = None
            return None
        if not isinstance(user, dict):
            self._cached_login = None
            return None
        login = user.get("login")
        if not isinstance(login, str) or not login:
            self._cached_login = None
            return None
        self._cached_login = login
        return login

    def publish(self, body: str, fingerprint_key: str) -> None:
        """Create or update the bot-owned Guardian comment.

        - Paginates through all issue comment pages (bounded).
        - Only patches bot-owned comments (never contributor-authored).
        - Skips the update when the rendered body is unchanged.
        - Pagination uncertainty fails safely — never silently creates
          duplicates when an owned comment may exist on an unseen page.
        - *fingerprint_key* must be exactly 16 lowercase hex characters
          and must match the key in any existing owned comment's marker.
        """
        # Validate fingerprint_key
        if not _FINGERPRINT_RE.match(fingerprint_key):
            raise RuntimeError(
                "Invalid fingerprint key for Guardian comment."
            )

        # --- paginate through all comment pages -------------------------------
        all_comments: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        seen_urls: set[str] = set()
        pages_fetched = 0
        total_bytes = 0
        pagination_uncertain = False
        url = f"{self._base}/issues/{self._pull_number}/comments?per_page=100"

        while url and pages_fetched < MAX_COMMENT_PAGES:
            pages_fetched += 1

            # URL cycle detection — repeated URL across pages
            if url in seen_urls:
                pagination_uncertain = True
                break
            seen_urls.add(url)

            try:
                raw, next_url = self._json_with_link(url)
            except RuntimeError:
                pagination_uncertain = True
                break

            if not isinstance(raw, list):
                pagination_uncertain = True
                break

            for entry in raw:
                if not isinstance(entry, dict):
                    pagination_uncertain = True
                    continue
                eid = entry.get("id")
                if not isinstance(eid, int):
                    pagination_uncertain = True
                    continue
                if eid in seen_ids:
                    # Cycle detection — duplicate IDs across pages
                    pagination_uncertain = True
                    continue
                seen_ids.add(eid)
                all_comments.append(entry)

            # Estimate bytes — rough upper bound
            total_bytes += len(json.dumps(raw).encode("utf-8"))
            if total_bytes > MAX_COMMENT_BYTES:
                pagination_uncertain = True
                break

            if len(all_comments) > MAX_COMMENTS:
                pagination_uncertain = True
                break

            # Page cap exhaustion — there are more pages we can't fetch
            if pages_fetched >= MAX_COMMENT_PAGES and next_url:
                pagination_uncertain = True
                break

            # Phase 3 fail-closed: structural URL validation for pagination
            if next_url:
                expected_prefix = (
                    f"/repos/{self._repository}/issues/{self._pull_number}/comments"
                )
                try:
                    self._validate_next_url(next_url, expected_prefix)
                except RuntimeError:
                    pagination_uncertain = True
                    break
            url = next_url

        # Post-loop: if url is still set, we exited due to page cap without
        # fetching the remaining pages
        if url and not pagination_uncertain:
            pagination_uncertain = True

        # --- confirm authenticated identity ------------------------------------
        identity = self.authenticated_login()
        if identity is None:
            raise RuntimeError(
                "Cannot publish Guardian comment: authenticated bot identity "
                "could not be confirmed. The /user endpoint must return a "
                "valid login for the authenticated token."
            )

        # --- find owned comment ------------------------------------------------
        try:
            existing = find_owned_comment(all_comments, identity)
        except RuntimeError:
            raise RuntimeError(
                "Cannot publish Guardian comment: multiple bot-owned "
                "Guardian comments exist (publication ambiguity)."
            )

        if existing:
            if not is_bot_comment(existing, identity):
                existing = None
            elif should_skip_update(existing, body):
                return  # identical — no-op

        # Pagination uncertainty → fail safe, never create/update
        if pagination_uncertain:
            raise RuntimeError(
                "Cannot publish Guardian comment: comment listing is incomplete "
                "or malformed. The assessment was evaluated but publication "
                "requires a complete comment listing."
            )

        if existing:
            self._json(
                f"{self._base}/issues/comments/{existing['id']}",
                method="PATCH",
                payload={"body": body},
            )
        else:
            self._json(
                f"{self._base}/issues/{self._pull_number}/comments",
                method="POST",
                payload={"body": body},
            )

    def _json_with_link(
        self, url: str, method: str = "GET", payload: dict[str, Any] | None = None
    ) -> tuple[Any, str]:
        """Return (parsed_json, next_url) where *next_url* is extracted from
        the ``Link`` response header or ``""`` when there is no next page.

        Raises sanitised RuntimeError on decode/parse failures — never
        includes raw response content in the error message.
        """
        raw, headers = self._request_with_headers(
            url, method=method, payload=payload
        )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise RuntimeError(
                "GitHub API response could not be decoded as UTF-8"
            )
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(
                "GitHub API response contained malformed JSON"
            )
        next_url = ""
        link = headers.get("Link", "")
        if link and isinstance(link, str):
            next_url = self._parse_link_header(link)
        return result, next_url

    def _json(
        self, url: str, method: str = "GET", payload: dict[str, Any] | None = None
    ) -> Any:
        raw = self._request(url, method=method, payload=payload)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise RuntimeError(
                "GitHub API response could not be decoded as UTF-8"
            )
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError(
                "GitHub API response contained malformed JSON"
            )

    @staticmethod
    def _sleep(seconds: float) -> None:
        """Sleep for *seconds*.  Overridden in tests for determinism."""
        time.sleep(seconds)

    @staticmethod
    def _is_retryable(method: str, code: int | None) -> bool:
        """Return True when the request is safe to retry.

        Only idempotent GET requests that receive a transient status
        (429 or 5xx) are retried.  Mutation methods are never retried.
        """
        if method != "GET":
            return False
        if code is None:
            return False
        return code == 429 or code >= 500

    @staticmethod
    def _validate_url(url: str) -> None:
        """Phase 3 fail-closed: structural URL validation via :func:`urlparse`.

        Rejects any URL that is not exactly ``https://api.github.com/...``
        with no userinfo, port, or fragment.  The structural check cannot be
        tricked by hostname suffix/prefix attacks or encoded separators.

        Raises :class:`RuntimeError` (sanitised) on any violation,
        including when ``urlparse().port`` raises :class:`ValueError`
        for a non-numeric port component.
        """
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            raise RuntimeError(
                "Request URL is not a valid GitHub API endpoint"
            ) from exc

        if parsed.scheme != "https":
            raise RuntimeError("Request URL is not a valid GitHub API endpoint")
        if parsed.hostname != "api.github.com":
            raise RuntimeError("Request URL is not a valid GitHub API endpoint")
        try:
            if parsed.username is not None or parsed.password is not None:
                raise RuntimeError("Request URL is not a valid GitHub API endpoint")
            if parsed.port is not None:
                raise RuntimeError("Request URL is not a valid GitHub API endpoint")
        except ValueError as exc:
            # Non-numeric port component (e.g. api.github.com:bad)
            raise RuntimeError(
                "Request URL is not a valid GitHub API endpoint"
            ) from exc
        if parsed.fragment:
            raise RuntimeError("Request URL is not a valid GitHub API endpoint")

    @staticmethod
    def _validate_next_url(url: str, expected_path_prefix: str) -> None:
        """Phase 3 fail-closed: validate a pagination ``Link rel=next`` URL.

        The URL must satisfy all :meth:`_validate_url` constraints AND its
        path must equal *expected_path_prefix* exactly — never a startswith
        check that would accept sibling suffixes (``filesevil``,
        ``comments-other``).  Encoded slashes (``%2F``), dot segments
        (``/../``, ``/./``), and ``;params`` in the path are all rejected.

        The query string may vary — only the path is validated for
        structural equality.

        Raises :class:`RuntimeError` (sanitised) on any violation.
        """
        GitHubClient._validate_url(url)
        try:
            parsed = urlparse(url)
        except ValueError as exc:
            raise RuntimeError(
                "Pagination next-URL resource does not match expected endpoint"
            ) from exc

        # Phase 3 P1#1: exact structural path equality — never startswith
        if parsed.path != expected_path_prefix:
            raise RuntimeError(
                "Pagination next-URL resource does not match expected endpoint"
            )

        # Reject encoded-slash path transformations
        if "%2f" in parsed.path.lower():
            raise RuntimeError(
                "Pagination next-URL resource does not match expected endpoint"
            )

        # Reject dot segments
        if (
            "/../" in parsed.path
            or "/./" in parsed.path
            or parsed.path.endswith("/..")
            or parsed.path.endswith("/.")
            or parsed.path in ("/..", "/.")
        ):
            raise RuntimeError(
                "Pagination next-URL resource does not match expected endpoint"
            )

        # Reject ;params in the URL path component
        if parsed.params:
            raise RuntimeError(
                "Pagination next-URL resource does not match expected endpoint"
            )

    @staticmethod
    def _parse_link_header(link: str) -> str:
        """Parse an RFC 8288 ``Link`` response header.

        Returns the ``rel=\"next\"`` URL, or ``\"\"`` when there is no next
        page.  A non-empty *link* that cannot be parsed as a valid
        comma-separated sequence of ``<url>; param=value`` entries — or any
        entry with ambiguous ``rel=`` syntax — raises a sanitised
        :class:`RuntimeError`.  An empty/whitespace-only header is treated
        as no-next without error (the GitHub API sometimes omits the Link
        header entirely).

        Phase 3 P1#3 hardening:
        - Empty elements (trailing/leading/double commas) are rejected.
        - Multi-token quoted rel values (``\"next prev\"``) are rejected.
        - Unquoted rel with whitespace around ``=`` is rejected by the
          tightened ``_LINK_VALUE_RE`` regex.
        - Duplicate ``rel=next`` across entries is rejected.
        - Valid entries with no ``rel=next`` (e.g. only prev/last) return
          ``\"\"`` — the header is well-formed, this is the final page.
        """
        stripped = link.strip()
        if not stripped:
            return ""

        # Must begin with '<' — anything else is garbled
        if not stripped.startswith("<"):
            raise RuntimeError("Malformed Link header")

        # Split at top-level commas (respecting < > nesting and quoted strings)
        link_values: list[str] = []
        depth = 0
        in_quotes = False
        segment_start = 0
        for i, ch in enumerate(stripped):
            if ch == '"' and (i == 0 or stripped[i - 1] != "\\"):
                in_quotes = not in_quotes
            elif ch == "<":
                depth += 1
            elif ch == ">":
                depth -= 1
            elif ch == "," and depth == 0 and not in_quotes:
                link_values.append(stripped[segment_start:i].strip())
                segment_start = i + 1
        link_values.append(stripped[segment_start:].strip())

        next_url = ""
        for lv in link_values:
            # P1#3: empty element → malformed (trailing/leading/double comma)
            if not lv:
                raise RuntimeError("Malformed Link header")

            m = _LINK_VALUE_RE.fullmatch(lv)
            if not m:
                raise RuntimeError("Malformed Link header")

            url_candidate = m.group(1)
            params_str = m.group(2)

            # P1#3: reject empty URL in angle brackets
            if not url_candidate:
                raise RuntimeError("Malformed Link header")

            # --- Check rel= param -------------------------------------------------
            # Quoted rel= (RFC 8288 §3) — reject multi-token values
            quoted_rel_m = re.search(r';\s*rel="([^"]*)"', params_str)
            if quoted_rel_m is not None:
                rel_val = quoted_rel_m.group(1)
                # P1#3: reject multi-token rel like "next prev"
                if " " in rel_val:
                    raise RuntimeError("Malformed Link header")
                if rel_val == "next":
                    if next_url:
                        raise RuntimeError("Malformed Link header")
                    if not url_candidate.startswith("https://"):
                        raise RuntimeError("Malformed Link header")
                    next_url = url_candidate
            else:
                # Unquoted rel=value (RFC 8288 allows unquoted single-token values)
                # Tightened _LINK_VALUE_RE already rejects whitespace around =
                unquoted_rel_m = re.search(r';\s*rel=(\w+)', params_str)
                if unquoted_rel_m is not None:
                    rel_val = unquoted_rel_m.group(1)
                    if rel_val == "next":
                        if next_url:
                            raise RuntimeError("Malformed Link header")
                        if not url_candidate.startswith("https://"):
                            raise RuntimeError("Malformed Link header")
                        next_url = url_candidate

            # Reject ambiguous rel — more than one rel= on the same entry
            if len(_REL_ASSIGN_RE.findall(params_str)) > 1:
                raise RuntimeError("Malformed Link header")

        return next_url

    def _request_with_headers(
        self,
        url: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        accept: str = "application/vnd.github+json",
    ) -> tuple[bytes, dict[str, str]]:
        """Return (body, headers_dict) so callers can inspect Link headers.

        Bounded read, retry-on-transient for idempotent GET only, and
        sanitised error messages.  URL is validated before the
        Authorization header is attached.
        """
        # Validate URL before attaching Authorization (SSRF protection)
        self._validate_url(url)

        last_error: Exception | None = None
        for attempt in range(MAX_HTTP_RETRIES + 1):
            req = Request(url, method=method)
            req.add_header("Accept", accept)
            req.add_header("Authorization", f"Bearer {self._token}")
            req.add_header("X-GitHub-Api-Version", "2022-11-28")
            if payload is not None:
                req.add_header("Content-Type", "application/json")
                req.data = json.dumps(payload).encode("utf-8")
            try:
                with urlopen(req, timeout=20) as response:
                    body = _bounded_read(response)
                    headers = dict(response.headers.items())
                    return body, headers
            except HTTPError as error:
                last_error = error
                if attempt < MAX_HTTP_RETRIES and self._is_retryable(
                    method, error.code
                ):
                    # Parse Retry-After (capped at MAX_RETRY_DELAY)
                    retry_after = error.headers.get("Retry-After", "1")
                    try:
                        delay = min(float(retry_after), MAX_RETRY_DELAY)
                    except ValueError:
                        delay = 1.0
                    self._sleep(delay)
                    continue
                raise RuntimeError(
                    f"GitHub API request failed (status {error.code})"
                ) from error
            except RuntimeError:
                raise  # bounded-read errors are already sanitised
            except Exception as error:
                last_error = error
                if attempt < MAX_HTTP_RETRIES and method == "GET":
                    self._sleep(1.0)
                    continue
                raise RuntimeError(
                    "GitHub API request failed"
                ) from error

        raise RuntimeError("GitHub API request failed") from last_error

    def _request(
        self,
        url: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        accept: str = "application/vnd.github+json",
    ) -> bytes:
        body, _ = self._request_with_headers(url, method=method, payload=payload, accept=accept)
        return body
