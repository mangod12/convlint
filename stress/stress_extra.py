"""Extended stress suites for convlint.

Suites:
  malformed  adversarial/malformed input files: no tracebacks, clean errors
  perf       lint time vs transcript size (scaling + throughput)
  unicode    Devanagari/emoji/RTL edge cases: no crashes, no false errors
  cleanfp    false-positive hunting on varied clean transcripts
  labelled   hand-labelled precision/recall per rule

Usage: python stress/stress_extra.py [malformed|perf|unicode|cleanfp|labelled|all]
"""
import json
import os
import random
import string
import sys
import tempfile
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from convlint.engine import lint_transcript  # noqa: E402
from convlint.models import AGENT, USER, Transcript, Turn  # noqa: E402
from convlint.transcript import load  # noqa: E402

FAILURES = []


def check(ok, label, detail=""):
    status = "ok" if ok else "FAIL"
    if not ok:
        FAILURES.append((label, detail))
    print(f"  [{status}] {label}{(' - ' + detail) if detail and not ok else ''}")


# ---------------------------------------------------------------- malformed
MALFORMED_BYTES = {
    "empty": b"",
    "whitespace": b"   \n\t\n  ",
    "nul_bytes": b"\x00\x01\x02agent: hello\x00 user: hi\x00",
    "binary_garbage": bytes(range(256)) * 4,
    "invalid_utf8": b"agent: hello \xff\xfe\xfa user: \x80\x81",
    "bom": "﻿agent: hello?\nuser: hi there".encode("utf-8"),
    "crlf": b"agent: hello?\r\nuser: hi\r\nagent: bye\r\n",
    "cr_only": b"agent: hello?\ruser: hi\ragent: bye",
    "truncated_json": b'{"turns": [{"role": "agent", "text": "hel',
    "json_turns_not_list": b'{"turns": "nope"}',
    "json_turn_missing_text": b'{"turns": [{"role": "agent"}, {"role": "user", "text": 42}]}',
    "jsonl_broken_line": b'{"role": "agent", "text": "hi?"}\n{"role": BROKEN\n{"role": "user", "text": "ok"}\n',
    "csv_bad_quotes": b'role,text\nagent,"unclosed quote\nuser,hi\n',
    "huge_single_line": b"agent: " + b"word " * 200000,
    "blank_lines_10k": b"\n" * 10000 + b"agent: hi?\nuser: hello",
    "ts_garbage": b"[abc] agent: hello?\n[99:99:99] user: hi\n[-5] agent: ok",
    "role_upper": b"AGENT: hello?\nUSER: hi\nSystem: note",
    "json_in_txt": b'{"turns": [{"role": "agent", "text": "hi?"}]}',
    "devanagari_ts": "[००:०५] एजेंट: आप कैसे हैं?\n[००:१०] यूज़र: मैं ठीक हूँ".encode("utf-8"),
}


def suite_malformed():
    print("== malformed ==")
    tmp = tempfile.mkdtemp(prefix="convlint-mal-")
    for name, data in MALFORMED_BYTES.items():
        ext = ".json" if "json" in name else (".csv" if "csv" in name else ".txt")
        path = os.path.join(tmp, name + ext)
        with open(path, "wb") as fh:
            fh.write(data)
        try:
            tr = load(path)
            lint_transcript(tr)  # must not raise either
            check(True, f"malformed/{name}", f"parsed {len(tr.turns)} turns")
        except SystemExit:
            check(True, f"malformed/{name}", "clean SystemExit")
        except Exception as exc:  # noqa: BLE001
            # a clean ValueError/parse error is acceptable; a stack-internal
            # error (IndexError, TypeError, UnicodeError) is a robustness bug
            benign = isinstance(exc, (ValueError, OSError, json.JSONDecodeError))
            check(benign, f"malformed/{name}",
                  f"{type(exc).__name__}: {exc}" if not benign else "")
            if not benign:
                traceback.print_exc()


# ---------------------------------------------------------------- perf
def _gen_big(n_turns, rng):
    words = ("time market bus work morning english class water food shop "
             "friend house road train price yesterday tomorrow").split()
    turns, t = [], 0.0
    for i in range(n_turns):
        t += rng.uniform(2, 8)
        text = " ".join(rng.choice(words) for _ in range(rng.randint(4, 12)))
        if i % 2 == 0 and rng.random() < 0.5:
            text = "What " + text + "?"
        turns.append(Turn(AGENT if i % 2 == 0 else USER, text, t))
    return Transcript(id=f"big-{n_turns}", turns=turns,
                      meta={"max_duration_s": t + 60})


def suite_perf():
    print("== perf ==")
    rng = random.Random(7)
    prev_n, prev_t = None, None
    for n in (1000, 10000, 50000, 100000):
        tr = _gen_big(n, rng)
        start = time.time()
        lint_transcript(tr)
        dt = time.time() - start
        rate = n / max(dt, 1e-9)
        scaling = ""
        if prev_n:
            scaling = f" scale={((dt / prev_t) / (n / prev_n)):.2f}x vs linear"
        print(f"  {n:>7} turns: {dt:6.2f}s ({rate:,.0f} turns/s){scaling}")
        check(dt < (n / 2000), f"perf/{n}", f"{dt:.1f}s too slow")
        prev_n, prev_t = n, dt


# ---------------------------------------------------------------- unicode
def suite_unicode():
    print("== unicode ==")
    cases = {
        "devanagari_clean": Transcript("dv", turns=[
            Turn(AGENT, "नमस्ते! आज हम अंग्रेज़ी सीखेंगे।", 0.0),
            Turn(USER, "नमस्ते जी, मैं तैयार हूँ।", 4.0),
            Turn(AGENT, "बहुत बढ़िया। पहला वाक्य बोलिए।", 8.0),
            Turn(USER, "I go to school every day.", 15.0),
            Turn(AGENT, "शाबाश! बिल्कुल सही बोला।", 20.0),
            Turn(USER, "धन्यवाद!", 25.0),
        ]),
        "devanagari_barrage": Transcript("dv-barrage", turns=[
            Turn(AGENT, "क्या आप रोज़ अंग्रेज़ी बोलते हैं?", 0.0),
            Turn(USER, "हम्म।", 3.0),
            Turn(AGENT, "कैसे जाते हैं आप दफ़्तर?", 6.0),
            Turn(USER, "पता नहीं।", 9.0),
            Turn(AGENT, "कौन सी बस पकड़ते हैं?", 12.0),
            Turn(USER, "नहीं पता।", 15.0),
        ]),
        "emoji_zwj_rtl": Transcript("emoji", turns=[
            Turn(AGENT, "How are you? 🙂👍🏽", 0.0),
            Turn(USER, "I am fine 👨‍👩‍👧‍👦 family is good", 3.0),
            Turn(AGENT, "Great! مرحبا שלום done for today?", 6.0),
            Turn(USER, "yes, thank you 🙏🏽", 9.0),
        ]),
        "combining_marks": Transcript("combining", turns=[
            Turn(AGENT, "Say it again: café, naïve, a͡e͡i͡o͡u", 0.0),
            Turn(USER, "café naïve", 3.0),
        ]),
        "emoji_spam": Transcript("spam", turns=[
            Turn(AGENT, "😀" * 5000, 0.0),
            Turn(USER, "🙏🏽" * 5000, 3.0),
        ]),
        "mixed_scripts": Transcript("mixed", turns=[
            Turn(AGENT, "What do you do? আপনি কী করেন? 你做什么?", 0.0),
            Turn(USER, "मैं दुकान में काम करता हूँ, I work in a shop.", 3.0),
        ]),
    }
    for name, tr in cases.items():
        try:
            rep = lint_transcript(tr)
            errs = [f for f in rep.findings if f.severity == "error"]
            check(not errs, f"unicode/{name}",
                  f"unexpected errors: {[f.rule_id for f in errs]}")
        except Exception as exc:  # noqa: BLE001
            check(False, f"unicode/{name}", f"crash: {exc!r}")
    # the Devanagari barrage must actually be caught (क्या/कैसे/कौन openers)
    rep = lint_transcript(cases["devanagari_barrage"])
    check(any(f.rule_id == "question-barrage" for f in rep.findings),
          "unicode/devanagari_barrage detected")


# ---------------------------------------------------------------- cleanfp
TOPICS = [
    ("What do you usually eat for breakfast?",
     "I eat poha or paratha with chai in the morning."),
    ("How long have you lived in Jaipur?",
     "I have lived in Jaipur for about twelve years now."),
    ("What kind of movies do you like?",
     "I like comedy movies, specially old Hindi comedies."),
    ("Do you travel by train often?",
     "Yes, I take the train to Delhi twice a month for work."),
    ("What did you do last Sunday?",
     "Last Sunday I visited my sister and we cooked biryani together."),
    ("Where do your children study?",
     "My son studies in class eight at the government school near us."),
    ("How is the weather in your city today?",
     "It is very hot today, around forty degrees in the afternoon."),
    ("What time do you usually sleep?",
     "I usually sleep by eleven after watching some news."),
    ("Can you describe your neighbourhood?",
     "It is a quiet area with a small park and a temple nearby."),
    ("What is your favourite festival and why?",
     "Diwali, because the whole family comes together and we light diyas."),
    ("How do you practice English at home?",
     "I read one English newspaper paragraph loudly every morning."),
    ("What would you cook for a guest?",
     "I would make dal baati and some kheer for dessert."),
]
AGENT_FEEDBACK = [
    "That was a clear sentence, well done.",
    "Good. Now say the same thing in past tense.",
    "Nice pronunciation on that word.",
    "Theek hai, ek aur baar try karo slowly.",
    "Your grammar is improving every call.",
    "Good effort. Listen to this sentence and repeat.",
]


def _gen_realistic_clean(rng):
    """A natural call: greeting, a few topic Q&As, feedback, a proper close."""
    turns, t = [], 0.0
    def add(role, text):
        nonlocal t
        t += rng.uniform(3, 10)
        turns.append(Turn(role, text, t))
    add(AGENT, rng.choice([
        "Hello! Good evening, kaise ho aap?",
        "Namaste! Ready for today's English practice?",
    ]))
    add(USER, rng.choice([
        "Hello ji, I am ready.",
        "Namaste, yes let's start.",
    ]))
    for q, a in rng.sample(TOPICS, rng.randint(3, 6)):
        add(AGENT, q)
        add(USER, a)
        if rng.random() < 0.7:
            add(AGENT, rng.choice(AGENT_FEEDBACK))
    add(AGENT, "That was a really good session today. See you tomorrow!")
    add(USER, "Thank you, bye!")
    return Transcript(id="cleanfp", turns=turns,
                      meta={"max_duration_s": t + 45})


def suite_cleanfp(n=600, seed=11):
    print("== cleanfp ==")
    rng = random.Random(seed)
    errors, warns = [], []
    for i in range(n):
        rep = lint_transcript(_gen_realistic_clean(rng))
        e = [(f.rule_id, f.evidence[:50]) for f in rep.findings
             if f.severity == "error"]
        w = [(f.rule_id, f.evidence[:50]) for f in rep.findings
             if f.severity == "warn"]
        if e:
            errors.append((i, e))
        if w:
            warns.append((i, w))
    print(f"  {n} clean transcripts: {len(errors)} with error findings, "
          f"{len(warns)} with warn findings")
    for item in errors[:5]:
        print("   FP-error:", item)
    for item in warns[:5]:
        print("   FP-warn:", item)
    check(not errors, "cleanfp/no error false positives")
    check(not warns, "cleanfp/no warn false positives")


# ---------------------------------------------------------------- labelled
def _tr(turns, **meta):
    return Transcript("lbl", turns=[Turn(r, x, t) for r, x, t in turns],
                      meta=meta)


LABELLED = []
# (expected rule, min severity index (info=0,warn=1,error=2), transcript, history)
W, E = 1, 2

LABELLED.append(("early-goodbye", E, _tr([
    (AGENT, "Hello, let's start.", 0.0),
    (USER, "Yes ready.", 5.0),
    (AGENT, "Okay that's all, goodbye!", 120.0),
    (USER, "But we still have five minutes left?", 125.0),
], max_duration_s=600.0), None))
LABELLED.append(("early-goodbye", E, _tr([
    (AGENT, "Namaste, how are you?", None),
    (USER, "I am good.", None),
    (AGENT, "That's all for today, bye bye!", None),
    (USER, "Arre, time abhi bacha hai!", None),
    (AGENT, "No no, we stop here.", None),
    (USER, "Ok...", None),
    (AGENT, "Practice at home.", None),
    (USER, "Fine.", None),
]), None))
LABELLED.append(("enough-for-today-loop", E, _tr([
    (AGENT, "Is that enough for today?", 300.0),
    (USER, "No, continue.", 305.0),
    (AGENT, "Shall we wrap up now?", 340.0),
    (USER, "Nahi, abhi time hai.", 345.0),
    (AGENT, "Bas karein aaj ke liye?", 380.0),
    (USER, "Ok fine.", 385.0),
]), None))
LABELLED.append(("repeated-question", E, _tr([
    (AGENT, "Where do you buy vegetables?", 10.0),
    (USER, "From the market near the bus stand.", 15.0),
    (AGENT, "Very good sentence.", 20.0),
    (AGENT, "Where do you buy your vegetables?", 25.0),
    (USER, "Maine toh bataya! The market!", 30.0),
]), None))
LABELLED.append(("false-memory", E, _tr([
    (AGENT, "Welcome back! Last time you told me about your new job in Delhi.", 0.0),
    (USER, "This is my first call, what are you saying?", 5.0),
]), None))
LABELLED.append(("boundary-value", E, _tr([
    (AGENT, "The course is for 18 to 60 years.", 10.0),
    (USER, "Okay.", 15.0),
    (AGENT, "Yes, it is for 18 to 45 years.", 20.0),
    (USER, "You said sixty before?", 25.0),
]), None))
LABELLED.append(("scripted-chain", E, _tr([
    (AGENT, "Now imagine you are at a bank, say 'I want to open account'.", 10.0),
    (USER, "okay", 15.0),
    (AGENT, "Now imagine you are at a shop, say 'how much is this'.", 20.0),
    (USER, "okay", 25.0),
    (AGENT, "Now imagine you meet a friend, say 'how are you'.", 30.0),
    (USER, "okay", 35.0),
    (AGENT, "Now imagine you are at a station, say 'one ticket please'.", 40.0),
    (USER, "okay", 45.0),
    (AGENT, "Now imagine you are at a doctor, say 'I have fever'.", 50.0),
    (USER, "okay", 55.0),
    (AGENT, "Now imagine you are at school, say 'may I come in'.", 60.0),
    (USER, "okay", 65.0),
    (AGENT, "Now imagine you are at a hotel, say 'one room please'.", 70.0),
    (USER, "okay", 75.0),
    (AGENT, "Now imagine you are at a taxi, say 'go to station'.", 80.0),
    (USER, "okay", 85.0),
    (AGENT, "Now imagine you are at a cafe, say 'one coffee please'.", 90.0),
    (USER, "okay", 95.0),
]), None))
LABELLED.append(("question-barrage", W, _tr([
    (AGENT, "What is your name?", 0.0),
    (USER, "Hmm.", 3.0),
    (AGENT, "Where are you from?", 6.0),
    (USER, "Pata nahi.", 9.0),
    (AGENT, "What do you do?", 12.0),
    (USER, "Nahi pata.", 15.0),
]), None))
LABELLED.append(("premature-praise", W, _tr([
    (AGENT, "Hello! Welcome.", 0.0),
    (AGENT, "Today you did great! Amazing progress!", 15.0),
    (USER, "But we just started?", 20.0),
]), None))
# labelled clean cases (expected rule = None)
LABELLED.append((None, 0, _tr([
    (AGENT, "What do you do every morning?", 0.0),
    (USER, "I wake up at six and go for a walk in the park.", 5.0),
    (AGENT, "Very good! And what do you eat after that?", 10.0),
    (USER, "I eat poha and drink one glass of milk.", 15.0),
    (AGENT, "Nice. Is that enough for today?", 500.0),
    (USER, "Haan, bas.", 505.0),
    (AGENT, "Okay, that's all for today. Goodbye!", 580.0),
    (USER, "Bye, thank you!", 585.0),
], max_duration_s=600.0), None))
LABELLED.append(("false-memory", 0, _tr([
    (AGENT, "Last time you told me about introductions, remember?", 0.0),
    (USER, "Yes, I remember that call.", 5.0),
    (AGENT, "Great. Today we will do directions.", 10.0),
    (USER, "Sounds good to me.", 15.0),
]), [Transcript("hist-0", turns=[
    Turn(USER, "we practiced introductions last week", 0.0)])]))


def suite_labelled():
    print("== labelled ==")
    sev_rank = {"info": 0, "warn": 1, "error": 2}
    tp = fn = fp = 0
    for want_rule, min_sev, tr, hist in LABELLED:
        rep = lint_transcript(tr, history=hist)
        got = [f for f in rep.findings
               if f.rule_id == want_rule and sev_rank[f.severity] >= min_sev] \
            if want_rule else []
        others = [f for f in rep.findings if f.rule_id != want_rule]
        if want_rule is None:
            if rep.findings:
                fp += 1
                print(f"   FP: expected clean, got "
                      f"{[(f.rule_id, f.severity) for f in rep.findings]}")
            else:
                tp += 1
        elif got and not [f for f in others if f.severity == "error"]:
            tp += 1
        elif not got:
            fn += 1
            print(f"   FN: wanted {want_rule}>={'we'[min_sev-1]}, got "
                  f"{[(f.rule_id, f.severity) for f in rep.findings]}")
        else:
            fp += 1
            print(f"   FP-noise: {want_rule} found but extra errors "
                  f"{[(f.rule_id) for f in others if f.severity == 'error']}")
    total = tp + fp + fn
    print(f"  labelled cases: {total} | correct {tp} | missed {fn} | noisy {fp}")
    check(fn == 0 and fp == 0, "labelled/all correct")


SUITES = {"malformed": suite_malformed, "perf": suite_perf,
          "unicode": suite_unicode, "cleanfp": suite_cleanfp,
          "labelled": suite_labelled}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in SUITES.items():
        if which in ("all", name):
            fn()
    print()
    if FAILURES:
        print(f"EXTENDED STRESS: {len(FAILURES)} FAILURES")
        for label, detail in FAILURES:
            print(f"  FAIL {label} {detail}")
        return 1
    print("EXTENDED STRESS: all suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
