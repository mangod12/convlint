"""Lint engine: run all rules over transcripts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import Report, Transcript
from .rules import all_rules


def lint_transcript(transcript: Transcript,
                    history: Optional[List[Transcript]] = None,
                    config: Optional[Dict[str, Any]] = None) -> Report:
    config = config or {}
    report = Report(transcript_id=transcript.id)
    thresholds = config.get("thresholds", {})
    for rule in all_rules(config):
        rule_cfg = thresholds.get(rule.id, {})
        for finding in rule.check(transcript, history=history, config=rule_cfg):
            report.findings.append(finding)
    order = {"error": 0, "warn": 1, "info": 2}
    report.findings.sort(key=lambda f: (f.turn_index if f.turn_index is not None else 10**9,
                                        order.get(f.severity, 3)))
    return report


def lint_many(transcripts: List[Transcript],
              history: Optional[List[Transcript]] = None,
              config: Optional[Dict[str, Any]] = None) -> List[Report]:
    return [lint_transcript(t, history=history, config=config) for t in transcripts]
