from __future__ import annotations

from pathlib import Path
import re

import yaml

from invariant_guardian.domain.models import Invariant


REQUIRED_SECTIONS = {
    "Rule": "rule",
    "Rationale": "rationale",
    "Violating examples": "violating_examples",
    "Acceptable examples": "acceptable_examples",
}


def load_invariants(directory: Path) -> tuple[list[Invariant], list[str]]:
    """Load valid invariant Markdown files and return non-fatal validation warnings."""
    invariants: list[Invariant] = []
    warnings: list[str] = []
    for path in sorted(directory.glob("*.md")):
        try:
            invariants.append(_parse_invariant(path))
        except (ValueError, yaml.YAMLError) as error:
            warnings.append(f"{path.name}: {error}")
    return invariants, warnings


def _parse_invariant(path: Path) -> Invariant:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError("missing YAML front matter")
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict):
        raise ValueError("front matter must be a mapping")
    sections = _sections(match.group(2))
    missing = [title for title in REQUIRED_SECTIONS if title not in sections]
    if missing:
        raise ValueError(f"missing required section(s): {', '.join(missing)}")
    return Invariant(
        **metadata,
        **{field: sections[title] for title, field in REQUIRED_SECTIONS.items()},
    )


def _sections(body: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", body, re.MULTILINE))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        result[match.group(1).strip()] = body[match.end() : end].strip()
    return result
