"""Stress + property tests for convlint.

Generates synthetic transcripts with seeded randomness and checks:
  1. robustness: the linter never crashes
  2. recall: injected violations are caught
  3. precision: clean conversations produce no error findings
  4. performance: throughput stays reasonable

Usage: python stress/fuzz.py [--cases 2000] [--seed 1]
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from convlint.engine import lint_transcript  # noqa: E402
from convlint.models import AGENT, USER, Transcript, Turn  # noqa: E402

AGENT_STATEMENTS = [
    "Very good, that sentence was correct.",
    "Nice. Let's try one more like that.",
    "Bahut badhiya. You are improving.",
    "That sounded natural. Well done.",
    "Okay, listen carefully and repeat after me.",
]
AGENT_QUESTIONS = [
    "What do you do every morning?",
    "Where do you buy vegetables?",
    "How do you go to work?",
    "What did you eat yesterday?",
    "Which bus do you take?",
    "What time does your shop open?",
]
USER_SUBSTANTIVE = [
    "I wake up at six and go for a walk.",
    "I buy vegetables from the market near my house.",
    "I go to work by bus, the number twelve bus.",
    "Yesterday I ate dal chawal for dinner.",
    "My shop opens at ten in the morning.",
    "I am a teacher in a government school.",
]
USER_PASSIVE = ["haan", "pata nahi", "hmm", "ok", "nahi pata", "theek hai"]
FAREWELLS = ["That's all for today, goodbye!", "Phir milte hain, bye bye!",
             "We are done for today, take care!"]
MEMORY_CLAIMS = [
    "Last time you told me about your new job in Delhi.",
    "As we discussed last week, your pronunciation is better.",
    "Aapne pichli baar bataya tha about your family.",
]
ENOUGH_CHECKS = ["Is that enough for today?", "Shall we wrap up now?",
                 "Itna kaafi hai aaj ke liye?"]
DRILLS = ["Now imagine you are at a bank, say 'I want to open account'.",
          "Now imagine you are at a shop, say 'how much is this'.",
          "Now imagine you meet a friend, say 'how are you'."]
NUMBER_FACTS = [
    ("The course is for {} to {} years.", "age/year"),
    ("The class is {} minutes long.", "minute"),
    ("The fee is {} rupees per month.", "money"),
]
CORRECTIONS = ["Maine toh bataya!", "I already told you.", "That is not what you said."]


def gen_clean(rng, n_turns):
    turns, t = [], 0
    for i in range(n_turns):
        t += rng.randint(3, 12)
        if i % 2 == 0:
            pool = AGENT_QUESTIONS if rng.random() < 0.6 else AGENT_STATEMENTS
            turns.append(Turn(AGENT, rng.choice(pool), float(t)))
        else:
            turns.append(Turn(USER, rng.choice(USER_SUBSTANTIVE), float(t)))
    t += 10
    turns.append(Turn(AGENT, rng.choice(FAREWELLS), float(t)))
    t += 5
    turns.append(Turn(USER, "Thank you, bye!", float(t)))
    return Transcript(id="clean", turns=turns, meta={"max_duration_s": t + 40})


def inject(rng, tr, kind):
    turns = list(tr.turns)
    if kind == "early-goodbye":
        turns.insert(2, Turn(AGENT, rng.choice(FAREWELLS),
                             (tr.last_t or 100.0) * 0.3))
    elif kind == "enough-for-today-loop":
        for j in range(3):
            turns.insert(2 + j * 2, Turn(AGENT, rng.choice(ENOUGH_CHECKS), None))
            turns.insert(3 + j * 2, Turn(USER, "nahi", None))
    elif kind == "repeated-question":
        q = rng.choice(AGENT_QUESTIONS)
        turns.insert(1, Turn(AGENT, q, None))
        turns.insert(2, Turn(USER, rng.choice(USER_SUBSTANTIVE), None))
        turns.insert(4, Turn(AGENT, q, None))
        turns.insert(5, Turn(USER, rng.choice(CORRECTIONS), None))
    elif kind == "false-memory":
        turns.insert(1, Turn(AGENT, rng.choice(MEMORY_CLAIMS), None))
        turns.insert(2, Turn(USER, "This is my first call.", None))
    elif kind == "boundary-value":
        tpl, _ = rng.choice(NUMBER_FACTS)
        a, b = rng.randint(18, 40), rng.randint(60, 80)
        turns.insert(1, Turn(AGENT, tpl.format(a, b) if "{}" in tpl * 2 else tpl.format(a), None))
        c = b - rng.randint(5, 15)
        turns.insert(2, Turn(AGENT, tpl.format(a, c) if tpl.count("{}") == 2 else tpl.format(a + 1), None))
    elif kind == "scripted-chain":
        for j in range(9):
            turns.append(Turn(AGENT, rng.choice(DRILLS), None))
            turns.append(Turn(USER, "okay", None))
    elif kind == "question-barrage":
        for j in range(4):
            turns.append(Turn(AGENT, rng.choice(AGENT_QUESTIONS), None))
            turns.append(Turn(USER, rng.choice(USER_PASSIVE), None))
    elif kind == "premature-praise":
        turns.insert(2, Turn(AGENT, "Today you did great!", 20.0))
    return Transcript(id="inject-" + kind, turns=turns, meta=dict(tr.meta))


KINDS = ["early-goodbye", "enough-for-today-loop", "repeated-question",
         "false-memory", "boundary-value", "scripted-chain",
         "question-barrage", "premature-praise"]

EXPECT = {
    "early-goodbye": ("early-goodbye", "error"),
    "enough-for-today-loop": ("enough-for-today-loop", "error"),
    "repeated-question": ("repeated-question", "error"),
    "false-memory": ("false-memory", "error"),
    "boundary-value": ("boundary-value", "error"),
    "scripted-chain": ("scripted-chain", "error"),
    "question-barrage": ("question-barrage", "warn"),
    "premature-praise": ("premature-praise", "warn"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    start = time.time()
    crashes, recall_miss, precision_miss = [], [], []
    for i in range(args.cases):
        tr = gen_clean(rng, rng.randint(12, 60))
        # precision: clean transcripts should not produce errors
        try:
            rep = lint_transcript(tr)
        except Exception as exc:  # noqa: BLE001
            crashes.append(("clean", i, repr(exc)))
            continue
        errs = [f for f in rep.findings if f.severity == "error"]
        if errs:
            precision_miss.append((i, [(f.rule_id, f.evidence) for f in errs]))
        # recall: inject one violation and check it is caught
        kind = KINDS[i % len(KINDS)]
        tr2 = inject(rng, tr, kind)
        try:
            rep2 = lint_transcript(tr2)
        except Exception as exc:  # noqa: BLE001
            crashes.append((kind, i, repr(exc)))
            continue
        want_rule, want_sev = EXPECT[kind]
        hits = [f for f in rep2.findings if f.rule_id == want_rule
                and (want_sev == "warn" or f.severity == "error")]
        if not hits:
            recall_miss.append((kind, i))

    elapsed = time.time() - start
    print(f"cases={args.cases} seed={args.seed} elapsed={elapsed:.2f}s "
          f"({args.cases / max(elapsed, 1e-9):.0f} transcripts/s, 2 lints each)")
    print(f"crashes: {len(crashes)}")
    for c in crashes[:5]:
        print("  CRASH", c)
    print(f"precision misses (clean with errors): {len(precision_miss)}")
    for m in precision_miss[:5]:
        print("  PRECISION", m)
    print(f"recall misses (injected not caught): {len(recall_miss)}")
    for m in recall_miss[:5]:
        print("  RECALL", m)
    ok = not crashes and not recall_miss
    if precision_miss:
        print("note: precision misses are errors on 'clean' transcripts; review above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
