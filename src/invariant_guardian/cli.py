from __future__ import annotations

import argparse
import json
from pathlib import Path

from invariant_guardian.action_runner import run
from invariant_guardian.application import assess_diff


def main() -> None:
    parser = argparse.ArgumentParser(description="Assess a Java diff against Markdown invariants.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    assess = subparsers.add_parser("assess")
    assess.add_argument("--invariants", required=True, type=Path)
    assess.add_argument("--diff", required=True, type=Path)
    subparsers.add_parser("run-action")
    args = parser.parse_args()
    if args.command == "assess":
        assessment = assess_diff(args.invariants, args.diff.read_text(encoding="utf-8"))
        print(json.dumps(assessment.model_dump(mode="json"), indent=2))
    elif args.command == "run-action":
        raise SystemExit(run())
