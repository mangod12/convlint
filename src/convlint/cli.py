"""convlint command line interface."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import __version__
from .config import load_config
from .engine import lint_many
from .models import Transcript
from .report import render_json, render_sarif, render_text
from .rules import all_rules
from .transcript import expand_paths, load


def _load_many(paths: List[str]) -> List[Transcript]:
    out = []
    for p in expand_paths(paths):
        try:
            out.append(load(p))
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"convlint: could not parse {p}: {exc}", file=sys.stderr)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="convlint",
        description="Deterministic linter for voice/chat agent transcripts. "
                    "No LLM judge. Hinglish-aware.")
    p.add_argument("--version", action="version", version=f"convlint {__version__}")
    sub = p.add_subparsers(dest="command")

    lint = sub.add_parser("lint", help="Lint transcript files or directories")
    lint.add_argument("paths", nargs="+", help="Transcript files or directories")
    lint.add_argument("--history", nargs="*", default=None,
                      help="Prior session files/dirs used to verify memory claims")
    lint.add_argument("--format", choices=("text", "json", "sarif"), default="text")
    lint.add_argument("--output", help="Write report to this file instead of stdout")
    lint.add_argument("--config", help="Path to .convlint.json")
    lint.add_argument("--fail-on", choices=("error", "warn", "never"),
                      default="error",
                      help="Exit 1 when findings of this severity or worse exist")
    lint.add_argument("--quiet", action="store_true",
                      help="Only print the summary line")

    rules = sub.add_parser("rules", help="List available rules")
    rules.add_argument("--config", help="Path to .convlint.json")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "rules":
        config = load_config(args.config)
        for rule in all_rules(config):
            print(f"{rule.id:24} [{rule.default_severity:5}] {rule.name}")
            print(f"{'':24} {rule.description}")
        return 0
    if args.command == "lint":
        config = load_config(args.config)
        transcripts = _load_many(args.paths)
        if not transcripts:
            print("convlint: no transcripts found", file=sys.stderr)
            return 2
        history = _load_many(args.history) if args.history else None
        reports = lint_many(transcripts, history=history, config=config)
        if args.format == "json":
            text = render_json(reports)
        elif args.format == "sarif":
            text = render_sarif(reports)
        else:
            text = render_text(reports)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        elif args.quiet and args.format == "text":
            c = {"error": 0, "warn": 0, "info": 0}
            for r in reports:
                for k, v in r.counts().items():
                    c[k] += v
            print(f"{len(reports)} transcripts · "
                  f"error {c['error']} · warn {c['warn']} · info {c['info']}")
        else:
            print(text)
        if args.fail_on == "never":
            return 0
        order = {"error": 2, "warn": 1, "info": 0}
        threshold = order[args.fail_on]
        worst = max((order[f.severity] for r in reports for f in r.findings),
                    default=-1)
        return 1 if worst >= threshold else 0
    build_parser().print_help()
    return 2
