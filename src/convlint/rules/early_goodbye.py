"""early-goodbye: agent ends the call while call time is still left, or
ignores the user saying time remains."""
from __future__ import annotations

from typing import Iterable, List, Optional

from ..hinglish import FAREWELL, TIME_LEFT_OBJECTION, any_match
from ..models import AGENT, USER, Finding, Transcript
from .base import Rule, register


@register
class EarlyGoodbye(Rule):
    id = "early-goodbye"
    name = "Early goodbye / wrap-up while time remains"
    description = (
        "Flags agent farewells before the call's time limit is nearly up, "
        "farewells far from the end of the transcript, and wrap-ups that "
        "happen right after the user says time is left."
    )
    default_severity = "error"

    def check(self, transcript: Transcript, history: Optional[List[Transcript]] = None,
              config: Optional[dict] = None) -> Iterable[Finding]:
        config = config or {}
        turns = transcript.turns
        n = len(turns)
        last_t = transcript.last_t
        max_dur = transcript.max_duration_s
        min_remaining_s = float(config.get("min_remaining_s", 90))
        # fraction of the call where a farewell is acceptable
        end_frac = float(config.get("end_fraction", 0.85))
        end_turn_window = int(config.get("end_turn_window", 3))

        farewell_idx = [i for i, t in enumerate(turns)
                        if t.role == AGENT and any_match(FAREWELL, t.text)]
        for i in farewell_idx:
            t = turns[i]
            # case 1: user just said time is left (within previous 2 user turns)
            prev_users = [j for j in range(max(0, i - 4), i) if turns[j].role == USER]
            for j in prev_users[-2:]:
                if any_match(TIME_LEFT_OBJECTION, turns[j].text):
                    yield self.finding(
                        "error",
                        "Agent wrapped up with a farewell right after the user said "
                        "time is left. Treat 'time left' as a cue to continue, not end.",
                        turn_index=i, evidence=t.text)
                    break
            else:
                # case 1b: user objects right after the farewell that time is left
                nxt_users = [j for j in range(i + 1, min(n, i + 4))
                             if turns[j].role == USER]
                if nxt_users and any_match(TIME_LEFT_OBJECTION,
                                           turns[nxt_users[0]].text):
                    yield self.finding(
                        "error",
                        "User objected right after the farewell that time is "
                        "left, but the agent ended the call anyway.",
                        turn_index=i, evidence=t.text)
                    continue
                # case 2: timed call, farewell well before the limit
                if t.t is not None and max_dur and t.t < max_dur - min_remaining_s \
                        and t.t < max_dur * end_frac:
                    yield self.finding(
                        "error",
                        f"Agent farewell at {int(t.t)}s of a {int(max_dur)}s call "
                        f"(more than {int(min_remaining_s)}s left).",
                        turn_index=i, evidence=t.text)
                # case 3: no timing; farewell far from the transcript end
                elif t.t is None and max_dur is None and i < n - 1 - end_turn_window:
                    yield self.finding(
                        "warn",
                        "Agent farewell appears well before the end of the transcript "
                        "(no timestamps or time limit to confirm it was the end).",
                        turn_index=i, evidence=t.text)
                elif last_t is not None and max_dur is None and t.t is not None \
                        and t.t < last_t - min_remaining_s:
                    yield self.finding(
                        "warn",
                        f"Agent farewell at {int(t.t)}s but the call continued to "
                        f"{int(last_t)}s.",
                        turn_index=i, evidence=t.text)

        # only the first farewell is reported per case to avoid pile-ons
