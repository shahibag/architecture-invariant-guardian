"""Minimal GitHub REST client — bot-owned comment protection, no PR checkout."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from invariant_guardian.context import MAX_CHANGED_FILES
from invariant_guardian.domain.models import ChangedFile
from invariant_guardian.rendering.comment import MARKER_PREFIX

BOT_LOGIN = "github-actions[bot]"


def is_bot_comment(comment: dict[str, Any], bot_login: str) -> bool:
    """Return True when *comment* was authored by the bot *and* contains
    the Guardian marker."""
    user = comment.get("user", {})
    if not isinstance(user, dict):
        return False
    login = user.get("login", "")
    if not isinstance(login, str):
        return False
    if login.lower() != bot_login.lower():
        return False
    body = comment.get("body", "")
    return isinstance(body, str) and MARKER_PREFIX in body


def find_owned_comment(
    comments: list[dict[str, Any]], bot_login: str
) -> dict[str, Any] | None:
    """Return the first bot-owned Guardian comment, or None.

    Contributor-authored comments with copied markers are never returned.
    """
    for comment in comments:
        if isinstance(comment, dict) and is_bot_comment(comment, bot_login):
            return comment
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

    def pull_diff(self) -> str:
        return self._request(
            f"{self._base}/pulls/{self._pull_number}",
            accept="application/vnd.github.v3.diff",
        ).decode("utf-8")

    def changed_files(self) -> list[ChangedFile]:
        """Fetch the PR file listing from the GitHub REST API, paginating
        through all pages up to the Phase 1 ceiling.

        Each file includes its per-file patch (bounded by GitHub).  No
        checkout or execution of PR code is performed.  Missing patches on
        modified or added in-scope files are recorded as ``patch_complete=False``.
        """
        result: list[ChangedFile] = []
        url = f"{self._base}/pulls/{self._pull_number}/files?per_page=100"
        while url:
            raw, next_url = self._json_with_link(url)
            if not isinstance(raw, list):
                break
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                filename = entry.get("filename", "")
                if not isinstance(filename, str) or not filename:
                    continue
                status = entry.get("status", "modified")
                if status not in ("added", "modified", "removed", "renamed"):
                    status = "modified"
                patch = entry.get("patch")
                patch_str = patch if isinstance(patch, str) else None
                # A missing patch on a non-removed file is a coverage gap
                patch_complete = not (
                    patch_str is None and status != "removed"
                )
                result.append(
                    ChangedFile(
                        path=filename,
                        status=status,  # type: ignore[arg-type]
                        patch=patch_str,
                        patch_complete=patch_complete,
                    )
                )
                # Fetch one record beyond the public ceiling so the engine can
                # distinguish exactly 200 files from a truncated PR listing.
                if len(result) > MAX_CHANGED_FILES:
                    return result
            url = next_url
        return result

    def write_invariants(self, destination: Path, ref: str, directory: str) -> None:
        listing = self._json(
            f"{self._base}/contents/{directory.lstrip('/')}?ref={ref}"
        )
        if not isinstance(listing, list):
            raise TypeError(f"{directory} is not a directory in the base repository")
        destination.mkdir(parents=True, exist_ok=True)
        for entry in listing:
            if entry.get("type") != "file" or not entry.get("name", "").endswith(".md"):
                continue
            contents = self._json(entry["url"])
            encoded = contents.get("content", "")
            (destination / entry["name"]).write_bytes(
                base64.b64decode(encoded.encode("ascii"))
            )

    def publish(self, body: str, fingerprint_key: str) -> None:
        """Create or update the bot-owned Guardian comment.

        - Only patches bot-owned comments (never contributor-authored).
        - Skips the update when the rendered body is unchanged.
        """
        comments_list = self._json(
            f"{self._base}/issues/{self._pull_number}/comments?per_page=100"
        )
        if not isinstance(comments_list, list):
            comments_list = []

        existing = find_owned_comment(comments_list, BOT_LOGIN)

        if existing:
            # Never patch a comment we don't own
            if not is_bot_comment(existing, BOT_LOGIN):
                # Fall through to create a new comment
                existing = None
            elif should_skip_update(existing, body):
                return  # identical — no-op

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
        the ``Link`` response header or ``""`` when there is no next page."""
        raw, headers = self._request_with_headers(
            url, method=method, payload=payload
        )
        result = json.loads(raw.decode("utf-8"))
        next_url = ""
        link = headers.get("Link", "")
        if link:
            match = re.search(r'<([^>]+)>;\s*rel="next"', link)
            if match:
                next_url = match.group(1)
        return result, next_url

    def _json(
        self, url: str, method: str = "GET", payload: dict[str, Any] | None = None
    ) -> Any:
        raw = self._request(url, method=method, payload=payload)
        return json.loads(raw.decode("utf-8"))

    def _request_with_headers(
        self,
        url: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        accept: str = "application/vnd.github+json",
    ) -> tuple[bytes, dict[str, str]]:
        """Return (body, headers_dict) so callers can inspect Link headers."""
        req = Request(url, method=method)
        req.add_header("Accept", accept)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if payload is not None:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(payload).encode("utf-8")
        try:
            with urlopen(req, timeout=20) as response:
                body = response.read()
                headers = dict(response.headers.items())
                return body, headers
        except HTTPError as error:
            raise RuntimeError(f"GitHub API returned {error.code}") from error

    def _request(
        self,
        url: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        accept: str = "application/vnd.github+json",
    ) -> bytes:
        body, _ = self._request_with_headers(url, method=method, payload=payload, accept=accept)
        return body
