import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from convlint.transcript import loads_csv, loads_json, loads_jsonl, loads_txt  # noqa: E402


class TestParsers(unittest.TestCase):
    def test_json_turns_list(self):
        t = loads_json('[{"role": "agent", "text": "hi"}, {"role": "user", "text": "hello"}]', "x")
        self.assertEqual(len(t.turns), 2)
        self.assertEqual(t.turns[0].role, "agent")

    def test_json_with_meta(self):
        t = loads_json('{"meta": {"max_duration_s": 600}, "turns": [{"role": "assistant", "text": "hi", "t": 3}]}', "x")
        self.assertEqual(t.max_duration_s, 600)
        self.assertEqual(t.turns[0].role, "agent")
        self.assertEqual(t.turns[0].t, 3.0)

    def test_jsonl(self):
        t = loads_jsonl('{"meta": {"max_duration_s": 300}}\n{"role": "user", "text": "haan"}\n', "x")
        self.assertEqual(t.max_duration_s, 300)
        self.assertEqual(len(t.turns), 1)
        self.assertEqual(t.turns[0].role, "user")

    def test_txt_with_timestamps(self):
        t = loads_txt("[01:05] Agent: Hello there\n[01:10] User: Hi\n", "x")
        self.assertEqual(t.turns[0].t, 65.0)
        self.assertEqual(t.turns[1].role, "user")
        self.assertEqual(t.last_t, 70.0)

    def test_txt_role_aliases(self):
        t = loads_txt("Learner: haan\nTutor: theek hai\n", "x")
        self.assertEqual(t.turns[0].role, "user")
        self.assertEqual(t.turns[1].role, "agent")

    def test_csv(self):
        t = loads_csv("role,text,t\nagent,hi,0\nuser,hello,2\n", "x")
        self.assertEqual(len(t.turns), 2)
        self.assertEqual(t.turns[1].t, 2.0)


if __name__ == "__main__":
    unittest.main()
