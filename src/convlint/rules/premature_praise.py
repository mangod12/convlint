"""premature-praise: farewell-sounding praise in the middle of a call."""
from __future__ import annotations

from typing import Iterable, List, Optional

from ..hinglish import PRAISE_FAREWELL, any_match
from ..models import AGENT, Finding, Transcript
from .base import Rule, register


@register
class PrematurePraise(Rule):
    id = "premature-praise"
    name = "Farewell-sounding praise mid-call"
    description = (
        "Flags lines like 'today you did great' away from the end of the call. "
        "They sound like a goodbye and learners often answer 'bas itna hi' and leave."
    )
    default_severity = "warn"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        config = config or {}
        end_frac = float(config.get("end_fraction", 0.85))
        turns = transcript.turns
        n = len(turns)
        last_t = transcript.last_t
        for i, t in enumerate(turns):
            if t.role != AGENT or not any_match(PRAISE_FAREWELL, t.text):
                continue
            if t.t is not None and last_t:
                if t.t < last_t * end_frac:
                    yield self.finding(
                        "warn",
                        "Farewell-sounding praise well before the end of the call.",
                        turn_index=i, evidence=t.text)
            elif i < (n - 1) * end_frac:
                yield self.finding(
                    "warn",
                    "Farewell-sounding praise in the middle of the call.",
                    turn_index=i, evidence=t.text)
