"""Deterministic fake GitHub transport for integration tests.

Never makes network calls — all responses come from in-memory saved data.
"""

from __future__ import annotations

from typing import Any


class FakeTransport:
    """A deterministic, in-memory GitHub API that serves saved responses.

    Each endpoint is registered with a list of (status_code, body, headers)
    tuples.  Successive calls to the same URL pattern consume responses in
    FIFO order, making pagination testing straightforward.

    The transport is injected by replacing ``GitHubClient._json`` and
    ``GitHubClient._json_with_link``, so the client's own HTTP layer is
    never reached.
    """

    def __init__(self) -> None:
        self._pages: dict[str, list[tuple[int, Any, dict[str, str]]]] = {}
        self._call_log: list[tuple[str, str, Any]] = []

    def register(
        self,
        url_pattern: str,
        status: int = 200,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Register a saved response for *url_pattern*.

        When *url_pattern* is a substring of the request URL, this
        response is returned.  The first matching registration for each
        call is consumed (FIFO).
        """
        if url_pattern not in self._pages:
            self._pages[url_pattern] = []
        self._pages[url_pattern].append(
            (status, body, headers or {})
        )

    def call_log(self) -> list[tuple[str, str, Any]]:
        """Return (url, method, payload) for every call made through the
        transport."""
        return list(self._call_log)

    def inject(self, client: Any) -> None:
        """Replace *client*'s ``_json`` and ``_json_with_link`` with
        this transport."""
        client._json = self._fake_json  # type: ignore[method-assign]
        client._json_with_link = self._fake_json_with_link  # type: ignore[method-assign]

    def _find_response(self, url: str) -> tuple[int, Any, dict[str, str]] | None:
        """Find and consume the next matching saved response."""
        for pattern, responses in self._pages.items():
            if pattern in url and responses:
                return responses.pop(0)
        return None

    def _fake_json(
        self,
        url: str,
        method: str = "GET",
        payload: Any = None,
    ) -> Any:
        self._call_log.append((url, method, payload))
        found = self._find_response(url)
        if found is None:
            # Default: return empty list
            return []
        status, body, _headers = found
        if status >= 400:
            raise RuntimeError(f"GitHub API request failed (status {status})")
        return body

    def _fake_json_with_link(
        self,
        url: str,
        method: str = "GET",
        payload: Any = None,
    ) -> tuple[Any, str]:
        self._call_log.append((url, method, payload))
        found = self._find_response(url)
        if found is None:
            return [], ""
        status, body, headers = found
        if status >= 400:
            raise RuntimeError(f"GitHub API request failed (status {status})")
        next_url = headers.get("Link", "")
        if next_url:
            # Extract URL from Link header: <url>; rel="next"
            import re
            match = re.search(r'<([^>]+)>;\s*rel="next"', next_url)
            if match:
                next_url = match.group(1)
            else:
                next_url = ""
        return body, next_url
