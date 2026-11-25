"""enough-for-today-loop: agent repeatedly asks whether to stop."""
from __future__ import annotations

from typing import Iterable, List, Optional

from ..hinglish import ENOUGH_CHECK, any_match
from ..models import AGENT, Finding, Transcript
from .base import Rule, register


@register
class EnoughForToday(Rule):
    id = "enough-for-today-loop"
    name = "Repeated 'is that enough for today?' check-outs"
    description = (
        "Flags an agent that asks 'shall we stop / is that enough / bas karein' "
        "again and again. One check is fine; repeated check-outs push the "
        "learner to end the call."
    )
    default_severity = "warn"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        config = config or {}
        warn_at = int(config.get("warn_at", 2))
        error_at = int(config.get("error_at", 3))
        hits = [i for i, t in enumerate(transcript.turns)
                if t.role == AGENT and any_match(ENOUGH_CHECK, t.text)]
        if len(hits) >= warn_at:
            severity = "error" if len(hits) >= error_at else self.default_severity
            first = hits[0]
            yield self.finding(
                severity,
                f"Agent asked to stop/wrap up {len(hits)} times "
                f"(turns {', '.join(str(i) for i in hits[:6])}).",
                turn_index=first,
                evidence=transcript.turns[first].text)
