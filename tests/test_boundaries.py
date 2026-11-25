"""Boundary-pinning tests: each test kills a specific surviving mutant
found by stress/mutation.py. Each pins a rule's exact threshold."""
import pytest

from convlint.engine import lint_transcript
from convlint.hinglish import is_passive_answer
from convlint.models import AGENT, USER, Transcript, Turn


def tr(turns, **meta):
    return Transcript("t", turns=[Turn(r, x, t) for r, x, t in turns], meta=meta)


def findings_for(transcript, rule_id, history=None):
    rep = lint_transcript(transcript, history=history)
    return [f for f in rep.findings if f.rule_id == rule_id]


# --- question_barrage: max_run is exactly 3 (kills >= -> >)
def test_barrage_exactly_three_fires():
    t = tr([(AGENT, "What is your name?", None), (USER, "hmm", None),
            (AGENT, "Where are you from?", None), (USER, "pata nahi", None),
            (AGENT, "What do you do?", None), (USER, "nahi pata", None)])
    assert findings_for(t, "question-barrage")


def test_barrage_two_does_not_fire():
    t = tr([(AGENT, "What is your name?", None), (USER, "hmm", None),
            (AGENT, "Where are you from?", None), (USER, "pata nahi", None)])
    assert not findings_for(t, "question-barrage")


# --- enough_for_today: warn_at=2, error_at=3 (kills >= -> >)
def test_enough_two_warns():
    t = tr([(AGENT, "Is that enough for today?", 0.0), (USER, "nahi", 5.0),
            (AGENT, "Shall we wrap up now?", 10.0), (USER, "ok", 15.0)])
    got = findings_for(t, "enough-for-today-loop")
    assert got and got[0].severity == "warn"


def test_enough_three_is_error():
    t = tr([(AGENT, "Is that enough for today?", 0.0), (USER, "nahi", 5.0),
            (AGENT, "Shall we wrap up now?", 10.0), (USER, "nahi", 15.0),
            (AGENT, "Bas karein aaj ke liye?", 20.0), (USER, "ok", 25.0)])
    got = findings_for(t, "enough-for-today-loop")
    assert got and got[0].severity == "error"


# --- early_goodbye timed boundary (kills - -> +, and end_frac * 0.5)
def test_goodbye_just_before_min_remaining_fires():
    # 600s call, min_remaining 90 -> limit 510s; farewell at 400s must fire
    t = tr([(AGENT, "Hello, let's begin.", 0.0),
            (AGENT, "That's all for today, goodbye!", 400.0),
            (USER, "But we were doing so well.", 405.0)],
           max_duration_s=600.0)
    got = findings_for(t, "early-goodbye")
    assert got and got[0].severity == "error"


def test_goodbye_near_limit_ok():
    # farewell at 570s of 600s call: inside the final 90s, no finding
    t = tr([(AGENT, "Hello, let's begin.", 0.0),
            (AGENT, "That's all for today, goodbye!", 570.0),
            (USER, "Bye!", 575.0)],
           max_duration_s=600.0)
    assert not findings_for(t, "early-goodbye")


def test_goodbye_inside_min_remaining_short_call_ok():
    # 300s call: min_remaining binds tighter than end_fraction.
    # Farewell at 250s (50s left) is acceptable; a +/- flip on
    # min_remaining_s would flag it. Kills the surviving mutant.
    t = tr([(AGENT, "Hello, let's begin.", 0.0),
            (AGENT, "That's all for today, goodbye!", 250.0),
            (USER, "Bye!", 255.0)],
           max_duration_s=300.0)
    assert not findings_for(t, "early-goodbye")


# --- early_goodbye untimed end_turn_window (kills - -> +)
def test_goodbye_untimed_far_from_end_warns():
    turns = [(AGENT, "Hello.", None), (AGENT, "That's all for today, bye!", None)]
    turns += [(USER, f"ok {i}", None) for i in range(8)]
    got = findings_for(tr(turns), "early-goodbye")
    assert got


def test_goodbye_untimed_at_end_ok():
    turns = [(AGENT, "Hello.", None)] + [(USER, f"ok {i}", None) for i in range(8)]
    turns += [(AGENT, "That's all for today, bye!", None), (USER, "bye", None)]
    assert not findings_for(tr(turns), "early-goodbye")


# --- repeated_question: 0.6 similarity threshold (kills 0.6 -> 0.99)
def test_repeated_partial_overlap_fires():
    t = tr([
        (AGENT, "Where do you buy vegetables and fruits?", 0.0),
        (USER, "From the market near the bus stand.", 5.0),
        (AGENT, "Good.", 8.0),
        (AGENT, "Where do you buy vegetables and fresh fruits?", 12.0),
        (USER, "From the market.", 17.0),
    ])
    assert findings_for(t, "repeated-question")


# --- false_memory history-novel path (kills //2 -> full len)
def test_false_memory_history_partial_novel_fires():
    history = [Transcript("hist-1",
                          turns=[Turn(USER, "last week we practiced introductions and greetings", 0.0)])]
    t = tr([
        (AGENT, "Last time you told me about introductions at your bank job.", 0.0),
        (USER, "Did I?", 5.0),
    ])
    got = findings_for(t, "false-memory", history=history)
    assert got and got[0].severity == "error"


# --- scripted_chain: warn_at=5, error_at=8 (kills >= -> > + 3)
def test_scripted_chain_at_threshold_fires():
    t = tr(sum([[(AGENT, f"Now imagine you are at place {j}, say 'hi'.", None),
                 (USER, "okay", None)] for j in range(5)], []))
    got = findings_for(t, "scripted-chain")
    assert got
    t4 = tr(sum([[(AGENT, f"Now imagine you are at place {j}, say 'hi'.", None),
                  (USER, "okay", None)] for j in range(4)], []))
    assert not findings_for(t4, "scripted-chain")


# --- premature_praise: severity is warn (kills warn -> info)
def test_premature_praise_severity_warn():
    t = tr([(AGENT, "Hello! Welcome.", 0.0),
            (AGENT, "Today you did great! Amazing progress!", 15.0),
            (USER, "But we just started?", 20.0)])
    got = findings_for(t, "premature-praise")
    assert got and got[0].severity == "warn"


# --- boundary_value: needs every number, not every other one (kills [::2])
def test_boundary_value_second_number_conflict():
    t = tr([
        (AGENT, "Fee is 500 rupees, course is 18 to 60 years.", 0.0),
        (USER, "Okay.", 5.0),
        (AGENT, "Fee is 500 rupees, course is 18 to 45 years.", 10.0),
    ])
    assert findings_for(t, "boundary-value")


# --- is_passive_answer: two-word passive answers count (kills <=2 -> <=1)
def test_two_word_passive_answer():
    assert is_passive_answer("haan ji")
    assert is_passive_answer("theek hai")
    assert not is_passive_answer("I go to the market")
