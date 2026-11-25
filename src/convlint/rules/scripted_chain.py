"""scripted-chain: repetitive 'now imagine X, say Y' drill loops."""
from __future__ import annotations

from typing import Iterable, List, Optional

from ..hinglish import IMAGINE_CHAIN
from ..models import AGENT, Finding, Transcript
from .base import Rule, register


@register
class ScriptedChain(Rule):
    id = "scripted-chain"
    name = "Repetitive 'now imagine X, say Y' drill chains"
    description = (
        "Flags an agent stuck in a scripted imagination drill: many turns of "
        "'now imagine X, say Y'. A few drills are fine; a long chain means the "
        "agent is running a script, not having a conversation."
    )
    default_severity = "warn"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        config = config or {}
        warn_at = int(config.get("warn_at", 5))
        error_at = int(config.get("error_at", 8))
        hits = [i for i, t in enumerate(transcript.turns)
                if t.role == AGENT and IMAGINE_CHAIN.search(t.text)]
        if len(hits) >= warn_at:
            severity = "error" if len(hits) >= error_at else self.default_severity
            yield self.finding(
                severity,
                f"{len(hits)} 'imagine X, say Y' drill turns in one call "
                f"(turns {', '.join(str(i) for i in hits[:8])}).",
                turn_index=hits[0],
                evidence=transcript.turns[hits[0]].text)
