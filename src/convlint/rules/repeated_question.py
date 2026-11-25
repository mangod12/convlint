"""repeated-question: agent re-asks a question the user already answered,
or keeps asking after the user corrected it."""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Set

from ..hinglish import CORRECTION, any_match, is_question
from ..models import AGENT, USER, Finding, Transcript
from .base import Rule, register

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did", "you",
    "your", "yours", "i", "me", "my", "we", "our", "to", "of", "in", "on",
    "at", "for", "and", "or", "but", "what", "why", "how", "when", "where",
    "which", "who", "can", "could", "would", "should", "shall", "will",
    "kya", "kaise", "kyu", "kyun", "kab", "kahan", "kaun", "aap", "aapka",
    "aapki", "apna", "tum", "tumhara", "hai", "hain", "ho", "tha", "thi",
    "क्या", "कैसे", "क्यों", "कब", "कहां", "कौन", "आप", "आपका", "आपकी",
}


def _content_words(text: str) -> Set[str]:
    words = re.findall(r"[A-Za-z']+|[ऀ-ॿ]+", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def _similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@register
class RepeatedQuestion(Rule):
    id = "repeated-question"
    name = "Repeated question after an answer or correction"
    description = (
        "Flags an agent asking substantially the same question twice after "
        "the user already answered it, and re-asking after an explicit "
        "correction ('I already told you', 'maine toh bataya')."
    )
    default_severity = "warn"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        config = config or {}
        sim_threshold = float(config.get("similarity", 0.6))
        turns = transcript.turns
        out: List[Finding] = []
        asked: List[tuple] = []  # (index, content words) of answered agent questions
        last_user_i: Optional[int] = None
        for i, t in enumerate(turns):
            if t.role == USER:
                if any_match(CORRECTION, t.text):
                    # find the most recent agent question
                    for j in range(i - 1, -1, -1):
                        if turns[j].role == AGENT and is_question(turns[j].text):
                            out.append(self.finding(
                                "error",
                                "User corrected the agent right after a question, "
                                "which usually means the agent repeated or ignored "
                                "an earlier answer.",
                                turn_index=j, evidence=turns[j].text))
                            break
                last_user_i = i
            elif t.role == AGENT and is_question(t.text):
                words = _content_words(t.text)
                if words:
                    for j, prev in asked:
                        sim = _similarity(words, prev)
                        if sim >= sim_threshold and last_user_i is not None and last_user_i > j:
                            out.append(self.finding(
                                "warn",
                                f"Agent re-asked substantially the same question "
                                f"as turn {j} after the user already answered it.",
                                turn_index=i, evidence=t.text))
                            break
                    asked.append((i, words))
        return out
