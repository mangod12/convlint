"""Core data model: turns, transcripts, findings, reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

AGENT = "agent"
USER = "user"

SEVERITIES = ("info", "warn", "error")
SEVERITY_WEIGHT = {"info": 0, "warn": 5, "error": 20}


@dataclass
class Turn:
    role: str            # "agent", "user", or a passthrough role like "system"
    text: str
    t: Optional[float] = None  # seconds from call start, when known


@dataclass
class Transcript:
    id: str
    turns: List[Turn] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def max_duration_s(self) -> Optional[float]:
        v = self.meta.get("max_duration_s") or self.meta.get("time_limit_s")
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
        return None

    @property
    def last_t(self) -> Optional[float]:
        times = [tr.t for tr in self.turns if tr.t is not None]
        return max(times) if times else None


@dataclass
class Finding:
    rule_id: str
    severity: str        # info | warn | error
    message: str
    turn_index: Optional[int] = None
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "message": self.message,
            "turn_index": self.turn_index,
            "evidence": self.evidence,
        }


@dataclass
class Report:
    transcript_id: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def score(self) -> int:
        penalty = sum(SEVERITY_WEIGHT[f.severity] for f in self.findings)
        return max(0, 100 - penalty)

    @property
    def grade(self) -> str:
        s = self.score
        if s >= 90:
            return "A"
        if s >= 75:
            return "B"
        if s >= 60:
            return "C"
        if s >= 40:
            return "D"
        return "F"

    def counts(self) -> Dict[str, int]:
        c = {"info": 0, "warn": 0, "error": 0}
        for f in self.findings:
            c[f.severity] += 1
        return c

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "score": self.score,
            "grade": self.grade,
            "counts": self.counts(),
            "findings": [f.to_dict() for f in self.findings],
        }
