from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from invariant_guardian.rendering.comment import MARKER_PREFIX


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

    def write_invariants(self, destination: Path, ref: str, directory: str) -> None:
        listing = self._json(
            f"{self._base}/contents/{directory.lstrip('/')}?ref={ref}"
        )
        if not isinstance(listing, list):
            raise ValueError(f"{directory} is not a directory in the base repository")
        destination.mkdir(parents=True, exist_ok=True)
        for entry in listing:
            if entry.get("type") != "file" or not entry.get("name", "").endswith(".md"):
                continue
            contents = self._json(f"{entry['url']}?ref={ref}")
            encoded = contents.get("content", "")
            (destination / entry["name"]).write_bytes(
                base64.b64decode(encoded.encode("ascii"))
            )

    def publish(self, body: str, fingerprint: str) -> None:
        comments = self._json(
            f"{self._base}/issues/{self._pull_number}/comments?per_page=100"
        )
        existing = next(
            (
                comment
                for comment in comments
                if MARKER_PREFIX in comment.get("body", "")
            ),
            None,
        )
        if existing and f"{MARKER_PREFIX}{fingerprint} -->" in existing["body"]:
            return
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

    def _json(
        self, url: str, method: str = "GET", payload: dict[str, Any] | None = None
    ) -> Any:
        raw = self._request(url, method=method, payload=payload)
        return json.loads(raw.decode("utf-8"))

    def _request(
        self,
        url: str,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        accept: str = "application/vnd.github+json",
    ) -> bytes:
        request = Request(url, method=method)
        request.add_header("Accept", accept)
        request.add_header("Authorization", f"Bearer {self._token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if payload is not None:
            request.add_header("Content-Type", "application/json")
            request.data = json.dumps(payload).encode("utf-8")
        try:
            with urlopen(request, timeout=20) as response:
                return response.read()
        except HTTPError as error:
            raise RuntimeError(f"GitHub API returned {error.code}") from error
