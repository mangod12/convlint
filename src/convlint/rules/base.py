"""Rule base class and registry."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Type

from ..models import Finding, Transcript


class Rule:
    id: str = "base"
    name: str = "base rule"
    description: str = ""
    default_severity: str = "warn"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        raise NotImplementedError

    def finding(self, severity: Optional[str] = None, message: str = "",
                turn_index: Optional[int] = None, evidence: str = "") -> Finding:
        return Finding(
            rule_id=self.id,
            severity=severity or self.default_severity,
            message=message,
            turn_index=turn_index,
            evidence=evidence.strip()[:200],
        )


_REGISTRY: Dict[str, Type[Rule]] = {}


def register(cls: Type[Rule]) -> Type[Rule]:
    _REGISTRY[cls.id] = cls
    return cls


def all_rules(config: Optional[dict] = None) -> List[Rule]:
    config = config or {}
    disabled = set(config.get("disable", []))
    overrides = config.get("severity_overrides", {})
    rules = []
    for rid, cls in sorted(_REGISTRY.items()):
        if rid in disabled:
            continue
        rule = cls()
        if rid in overrides:
            rule.default_severity = overrides[rid]
        rules.append(rule)
    return rules
