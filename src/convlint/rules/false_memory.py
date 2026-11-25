"""false-memory: agent claims memory of something the user never said."""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

from ..hinglish import FIRST_CALL, MEMORY_CLAIM, any_match
from ..models import AGENT, USER, Finding, Transcript
from .base import Rule, register

_CONTENT = re.compile(r"[A-Za-z']{4,}|[ऀ-ॿ]{2,}")


def _words(text: str) -> Set[str]:
    return {w.lower() for w in _CONTENT.findall(text)}


@register
class FalseMemory(Rule):
    id = "false-memory"
    name = "Claimed memory of something never said"
    description = (
        "Flags 'last time you told me X' claims. Error when the user says it "
        "is their first call, or when prior sessions are provided and none of "
        "the referenced content appears in them. Warns when no history is "
        "available to check the claim against."
    )
    default_severity = "warn"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        user_texts = [t.text for t in transcript.turns if t.role == USER]
        first_call = any(any_match(FIRST_CALL, t) for t in user_texts)
        history_words: Set[str] = set()
        if history:
            for h in history:
                if h.id == transcript.id:
                    continue
                for t in h.turns:
                    if t.role == USER:
                        history_words |= _words(t.text)
        for i, t in enumerate(transcript.turns):
            if t.role != AGENT or not any_match(MEMORY_CLAIM, t.text):
                continue
            if first_call:
                yield self.finding(
                    "error",
                    "Agent claims memory of a past conversation but the user said "
                    "this is their first call.",
                    turn_index=i, evidence=t.text)
            elif history is not None:
                claim_words = _words(t.text)
                novel = {w for w in claim_words if w not in history_words}
                if len(novel) >= max(1, len(claim_words) // 2):
                    yield self.finding(
                        "error",
                        "Agent references past conversation content that does not "
                        "appear in any provided prior session.",
                        turn_index=i, evidence=t.text)
                else:
                    yield self.finding(
                        "info",
                        "Memory claim is consistent with provided history.",
                        turn_index=i, evidence=t.text)
            else:
                yield self.finding(
                    "warn",
                    "Memory claim cannot be verified: pass prior sessions with "
                    "--history to check it.",
                    turn_index=i, evidence=t.text)
