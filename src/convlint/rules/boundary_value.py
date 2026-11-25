"""boundary-value: numeric facts the agent contradicts or re-asserts after a
user correction (the '18/70' class of bug)."""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set

from ..hinglish import CORRECTION, any_match
from ..models import AGENT, USER, Finding, Transcript
from .base import Rule, register

_DIM = re.compile(
    r"(?P<num>\d{1,4})\s*(?:-|to|–|—)\s*(?P<num2>\d{1,4})\s*"
    r"(?P<unit>years?|yrs?|yr|sal( |)aa|saal|minutes?|mins?|seconds?|secs?|"
    r"hours?|hrs?|rupees?|rs\.?|inr|percent|%|kms?|kilometres?|meters?|kgs?|"
    r"kilograms?|साल|मिनट|घंटे|सेकंड|रुपये|किलो)|"
    r"(?P<num1>\d{1,4})\s*"
    r"(?P<unit1>years?|yrs?|yr|sal( |)aa|saal|minutes?|mins?|seconds?|secs?|"
    r"hours?|hrs?|rupees?|rs\.?|inr|percent|%|kms?|kilometres?|meters?|kgs?|"
    r"kilograms?|साल|मिनट|घंटे|सेकंड|रुपये|किलो)",
    re.IGNORECASE)

_BARE_NUM = re.compile(r"\b\d{1,4}\b")


def _dim_key(unit: str) -> str:
    u = unit.lower().strip()
    if u.startswith(("year", "yr", "sal", "saal", "साल")):
        return "age/year"
    if u.startswith(("min", "मिनट")):
        return "minute"
    if u.startswith(("sec", "सेकंड")):
        return "second"
    if u.startswith(("hour", "hr", "घंटे")):
        return "hour"
    if u.startswith(("rupee", "rs", "inr", "रुपये")):
        return "money"
    if u in ("%", "percent"):
        return "percent"
    return "other"


def _numbers(text: str) -> Dict[str, Set[int]]:
    """Extract dimensioned numbers: {'age/year': {18, 70}, 'minute': {3}}."""
    out: Dict[str, Set[int]] = {}
    for m in _DIM.finditer(text):
        if m.group("unit") is not None:
            key = _dim_key(m.group("unit"))
            vals = {int(m.group("num")), int(m.group("num2"))}
        else:
            key = _dim_key(m.group("unit1"))
            vals = {int(m.group("num1"))}
        out.setdefault(key, set()).update(vals)
    return out


@register
class BoundaryValue(Rule):
    id = "boundary-value"
    name = "Contradicted numeric boundary values"
    description = (
        "Flags numeric facts (ages, limits, prices, durations) the agent "
        "states inconsistently within a call, and values the agent re-asserts "
        "after the user corrected them."
    )
    default_severity = "error"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        out: List[Finding] = []
        agent_facts: Dict[str, Set[int]] = {}
        agent_last: Dict[str, Set[int]] = {}  # most recent stated set per dim
        last_dim: Optional[str] = None  # most recently stated dimension
        # dimension -> (user's disputed numbers, agent's claim at correction time)
        corrected: Dict[str, tuple] = {}

        for i, t in enumerate(transcript.turns):
            nums = _numbers(t.text)
            if t.role == USER:
                if any_match(CORRECTION, t.text):
                    dims = dict(nums)
                    bare = {int(b) for b in _BARE_NUM.findall(t.text)}
                    bare -= {v for vs in nums.values() for v in vs}
                    for b in bare:
                        matched = False
                        for k, claimed in agent_facts.items():
                            if b in claimed:
                                dims.setdefault(k, set()).add(b)
                                matched = True
                        if not matched and last_dim:
                            dims.setdefault(last_dim, set()).add(b)
                    for k, vals in dims.items():
                        prior = set(agent_last.get(k, set()))
                        corrected[k] = (set(vals), prior)
                continue
            if t.role != AGENT:
                continue
            for k, vals in nums.items():
                known = agent_facts.setdefault(k, set())
                if k in corrected:
                    user_vals, prior_claim = corrected[k]
                    # agent re-asserts the exact claim the user disputed
                    if vals == prior_claim and not (vals & user_vals):
                        out.append(self.finding(
                            "error",
                            f"Agent re-asserted the {k} value {sorted(prior_claim)} "
                            f"that the user had just disputed.",
                            turn_index=i, evidence=t.text))
                # agent contradicts its own earlier statement in the same call:
                # both sides have values the other lacks
                if known and not (vals <= known) and not (known <= vals):
                    out.append(self.finding(
                        "error",
                        f"Agent states conflicting {k} values: "
                        f"{sorted(known)} earlier, {sorted(vals)} here.",
                        turn_index=i, evidence=t.text))
                known.update(vals)
                agent_last[k] = set(vals)
                last_dim = k
        # dedupe identical (message, turn) findings
        seen = set()
        for f in out:
            key = (f.message, f.turn_index)
            if key not in seen:
                seen.add(key)
                yield f
