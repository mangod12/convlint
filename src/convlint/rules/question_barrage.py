"""question-barrage: many agent questions in a row with no substantive reply."""
from __future__ import annotations

from typing import Iterable, List, Optional

from ..hinglish import is_passive_answer, is_question
from ..models import AGENT, USER, Finding, Transcript
from .base import Rule, register


@register
class QuestionBarrage(Rule):
    id = "question-barrage"
    name = "Question barrage against a passive learner"
    description = (
        "Flags runs of agent questions where the learner gives only short, "
        "low-content answers ('haan', 'pata nahi') or nothing at all. A "
        "passive learner needs modeling and statements, not another question."
    )
    default_severity = "warn"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        config = config or {}
        max_run = int(config.get("max_consecutive", 3))
        out: List[Finding] = []
        current: List[int] = []

        def flush() -> None:
            if len(current) >= max_run:
                out.append(self.finding(
                    "warn",
                    f"{len(current)} consecutive agent questions with no "
                    f"substantive learner reply.",
                    turn_index=current[0],
                    evidence=transcript.turns[current[0]].text))
            current.clear()

        for i, t in enumerate(transcript.turns):
            if t.role == AGENT and is_question(t.text):
                current.append(i)
            elif t.role == USER and is_passive_answer(t.text):
                continue  # barrage continues
            else:
                flush()
        flush()
        return out
