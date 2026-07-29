from __future__ import annotations

import re
from collections.abc import Iterable

from invariant_guardian.domain.models import CandidateFinding

TEMPORARY_MONITORING_ID = "no-temporary-monitoring"
DOMAIN_LEAK_ID = "no-domain-leak"

_MONITORING_PATTERNS = {
    "scheduled work": re.compile(r"@Scheduled|ScheduledExecutorService"),
    "wait retry": re.compile(r"Thread\.sleep|TimeUnit\.[A-Z_]+\.sleep"),
    "state polling": re.compile(r"while\s*\(|for\s*\(\s*;"),
}
_STATE_CHANGE = re.compile(r"\b(save|update|setStatus|transition|publishEvent|emit)\b")
_PUBLIC_BOUNDARY = re.compile(r"\bpublic\s+[A-Za-z0-9_<>?, ]+\s+[A-Za-z0-9_]+\s*\(")
_INTERNAL_TYPE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(Entity|Aggregate|PersistenceModel)\b")


def detect_candidates(diff: str, enabled_ids: Iterable[str]) -> list[CandidateFinding]:
    enabled = set(enabled_ids)
    findings: list[CandidateFinding] = []
    for path, line_number, line in _added_lines(diff):
        if not path.endswith(".java"):
            continue
        if TEMPORARY_MONITORING_ID in enabled:
            for name, pattern in _MONITORING_PATTERNS.items():
                if pattern.search(line) and _STATE_CHANGE.search(diff):
                    findings.append(
                        CandidateFinding(
                            invariant_id=TEMPORARY_MONITORING_ID,
                            file=path,
                            start_line=line_number,
                            end_line=line_number,
                            pattern=name,
                            evidence=line.strip(),
                            confidence="medium",
                        )
                    )
                    break
        if (
            DOMAIN_LEAK_ID in enabled
            and _PUBLIC_BOUNDARY.search(line)
            and (type_match := _INTERNAL_TYPE.search(line))
        ):
            findings.append(
                CandidateFinding(
                    invariant_id=DOMAIN_LEAK_ID,
                    file=path,
                    start_line=line_number,
                    end_line=line_number,
                    pattern="public boundary exposes likely internal type",
                    evidence=f"{line.strip()} (matched {type_match.group(0)})",
                    confidence="medium",
                )
            )
    return findings


def _added_lines(diff: str) -> Iterable[tuple[str, int, str]]:
    path: str | None = None
    new_line: int | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line.removeprefix("+++ b/")
        elif line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line = int(match.group(1)) if match else None
        elif path and new_line is not None:
            if line.startswith("+") and not line.startswith("+++"):
                yield path, new_line, line[1:]
                new_line += 1
            elif line.startswith(" "):
                new_line += 1
