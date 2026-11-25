import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from convlint.engine import lint_transcript  # noqa: E402
from convlint.transcript import loads_json, loads_txt  # noqa: E402


def lint(text, fmt="txt", **meta):
    if fmt == "json":
        t = loads_json(text, "t")
    else:
        t = loads_txt(text, "t")
    t.meta.update(meta)
    return lint_transcript(t)


def rule_ids(report):
    return {f.rule_id for f in report.findings}


class TestEarlyGoodbye(unittest.TestCase):
    def test_farewell_before_limit_flags(self):
        r = lint("[00:00] Agent: Hi\n[00:10] Agent: That's all for today, goodbye!\n", max_duration_s=600)
        self.assertIn("early-goodbye", rule_ids(r))
        self.assertTrue(any(f.severity == "error" for f in r.findings))

    def test_farewell_at_end_ok(self):
        r = lint("[09:30] Agent: Great work.\n[09:50] Agent: Goodbye, take care!\n[09:55] User: bye\n", max_duration_s=600)
        self.assertNotIn("early-goodbye", rule_ids(r))

    def test_time_left_objection_flags(self):
        r = lint("[00:10] User: abhi toh time hai, why stop?\n[00:15] Agent: Bye bye, take care!\n", max_duration_s=600)
        errs = [f for f in r.findings if f.rule_id == "early-goodbye" and f.severity == "error"]
        self.assertTrue(errs)


class TestEnoughForToday(unittest.TestCase):
    def test_repeated_checkouts(self):
        r = lint(
            "[00:10] Agent: Is that enough for today?\n[00:15] User: nahi\n"
            "[00:20] Agent: Shall we wrap up? Itna kaafi hai?\n[00:25] User: ok\n"
            "[00:30] Agent: Should we stop now?\n")
        f = [f for f in r.findings if f.rule_id == "enough-for-today-loop"]
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "error")

    def test_single_checkout_ok(self):
        r = lint("[09:40] Agent: Shall we wrap up for today?\n[09:45] User: haan bye\n")
        self.assertNotIn("enough-for-today-loop", rule_ids(r))


class TestRepeatedQuestion(unittest.TestCase):
    def test_correction_flags(self):
        r = lint("[00:05] Agent: What do you do for work?\n[00:10] User: Maine toh bataya!\n")
        errs = [f for f in r.findings if f.rule_id == "repeated-question" and f.severity == "error"]
        self.assertTrue(errs)

    def test_same_question_twice_after_answer(self):
        r = lint(
            "[00:05] Agent: What is your favourite food?\n[00:10] User: I love biryani.\n"
            "[00:20] Agent: What is your favourite food?\n")
        warns = [f for f in r.findings if f.rule_id == "repeated-question"]
        self.assertTrue(warns)

    def test_different_questions_ok(self):
        r = lint(
            "[00:05] Agent: What is your name?\n[00:10] User: Ramesh Kumar from Patna.\n"
            "[00:20] Agent: What do you do in Patna?\n")
        self.assertNotIn("repeated-question", rule_ids(r))


class TestFalseMemory(unittest.TestCase):
    def test_first_call_claim_is_error(self):
        r = lint("[00:00] Agent: Last time you told me about your shop.\n[00:06] User: This is my first call.\n")
        errs = [f for f in r.findings if f.rule_id == "false-memory" and f.severity == "error"]
        self.assertTrue(errs)

    def test_unverifiable_warns(self):
        r = lint("[00:20] Agent: As we discussed last week, your grammar improved.\n")
        f = [f for f in r.findings if f.rule_id == "false-memory"]
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "warn")


class TestBoundaryValue(unittest.TestCase):
    def test_conflicting_bounds(self):
        r = lint("[00:00] Agent: Course is for 18 to 70 years.\n[00:10] Agent: Limit is 18 to 60 years only.\n")
        errs = [f for f in r.findings if f.rule_id == "boundary-value" and f.severity == "error"]
        self.assertTrue(errs)

    def test_restating_subset_ok(self):
        r = lint("[00:00] Agent: Course is for 18 to 70 years.\n[00:10] Agent: Yes, 70 years is the max.\n")
        self.assertNotIn("boundary-value", rule_ids(r))

    def test_reassert_after_dispute(self):
        r = lint(
            "[00:00] Agent: Limit is 18 to 60 years.\n[00:06] User: That is not what you said, you said 70.\n"
            "[00:12] Agent: No, limit is 18 to 60 years.\n")
        errs = [f for f in r.findings if f.rule_id == "boundary-value" and f.severity == "error"]
        self.assertTrue(errs)


class TestScriptedChain(unittest.TestCase):
    def test_long_chain_flags(self):
        lines = []
        for k in range(9):
            lines.append(f"[00:{k:02d}] Agent: Now imagine you are at place {k}, say 'hello {k}'.")
            lines.append(f"[00:{k:02d}30] User: hello {k}")
        r = lint("\n".join(lines) + "\n")
        f = [f for f in r.findings if f.rule_id == "scripted-chain"]
        self.assertTrue(f)
        self.assertEqual(f[0].severity, "error")

    def test_short_chain_ok(self):
        r = lint(
            "[00:00] Agent: Now imagine you are at a shop, say 'how much is this'.\n[00:05] User: how much is this\n")
        self.assertNotIn("scripted-chain", rule_ids(r))


class TestQuestionBarrage(unittest.TestCase):
    def test_passive_barrage(self):
        r = lint(
            "[00:00] Agent: What do you do?\n[00:03] User: pata nahi\n"
            "[00:05] Agent: Where do you live?\n[00:08] User: haan\n"
            "[00:10] Agent: Do you like English?\n")
        self.assertIn("question-barrage", rule_ids(r))

    def test_engaged_learner_ok(self):
        r = lint(
            "[00:00] Agent: What do you do?\n[00:03] User: I run a small kirana shop in my village.\n"
            "[00:08] Agent: Where do you live?\n[00:12] User: Near the old bus stand, with my family.\n")
        self.assertNotIn("question-barrage", rule_ids(r))


class TestPrematurePraise(unittest.TestCase):
    def test_mid_call_praise(self):
        r = lint("[00:30] Agent: Today you did great!\n[05:00] User: bas itna hi?\n")
        self.assertIn("premature-praise", rule_ids(r))

    def test_end_praise_ok(self):
        r = lint("[09:40] Agent: Today you did great!\n[09:50] User: thank you bye\n")
        self.assertNotIn("premature-praise", rule_ids(r))


class TestScoring(unittest.TestCase):
    def test_clean_is_100(self):
        r = lint("[00:00] Agent: Hi, how are you?\n[00:04] User: I am good, learning English.\n")
        self.assertEqual(r.score, 100)
        self.assertEqual(r.grade, "A")

    def test_error_drops_score(self):
        r = lint("[00:00] Agent: That's all for today, goodbye!\n[00:10] User: ok bye\n", max_duration_s=600)
        self.assertLessEqual(r.score, 80)


if __name__ == "__main__":
    unittest.main()
