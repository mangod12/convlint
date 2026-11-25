"""Report rendering: text, json, sarif."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from . import __version__
from .models import Report

_SARIF_LEVEL = {"error": "error", "warn": "warning", "info": "note"}


def render_text(reports: List[Report]) -> str:
    lines: List[str] = []
    for r in reports:
        c = r.counts()
        lines.append(f"{r.transcript_id}: score {r.score}/100 ({r.grade})  "
                     f"[error {c['error']} · warn {c['warn']} · info {c['info']}]")
        for f in r.findings:
            where = f"turn {f.turn_index}" if f.turn_index is not None else "transcript"
            lines.append(f"  {f.severity.upper():5} {f.rule_id} ({where}): {f.message}")
            if f.evidence:
                snippet = f.evidence if len(f.evidence) <= 120 else f.evidence[:117] + "..."
                lines.append(f"        > {snippet}")
        if not r.findings:
            lines.append("  clean")
    if len(reports) > 1:
        worst = min(r.score for r in reports)
        avg = sum(r.score for r in reports) / len(reports)
        lines.append(f"\n{len(reports)} transcripts · avg score {avg:.0f} · worst {worst}")
    return "\n".join(lines)


def render_json(reports: List[Report]) -> str:
    return json.dumps({
        "tool": "convlint",
        "version": __version__,
        "reports": [r.to_dict() for r in reports],
    }, indent=2, ensure_ascii=False)


def render_sarif(reports: List[Report]) -> str:
    results = []
    rules = {}
    for r in reports:
        for f in r.findings:
            rules.setdefault(f.rule_id, {
                "id": f.rule_id,
                "name": f.rule_id.replace("-", " ").title().replace(" ", ""),
                "shortDescription": {"text": f.rule_id},
            })
            results.append({
                "ruleId": f.rule_id,
                "level": _SARIF_LEVEL.get(f.severity, "warning"),
                "message": {"text": f"{f.message} {f.evidence}".strip()},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": r.transcript_id},
                        **({"region": {"startLine": f.turn_index + 1}}
                           if f.turn_index is not None else {}),
                    }
                }],
            })
    sarif: Dict[str, Any] = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "convlint",
                "version": __version__,
                "rules": list(rules.values()),
            }},
            "results": results,
        }],
    }
    return json.dumps(sarif, indent=2, ensure_ascii=False)
