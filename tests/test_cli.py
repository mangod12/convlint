import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from convlint.cli import main  # noqa: E402

EX = os.path.join(os.path.dirname(__file__), "..", "examples")


class TestCli(unittest.TestCase):
    def test_lint_examples_json(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out.json")
            rc = main(["lint", EX, "--format", "json", "--output", out])
            self.assertEqual(rc, 1)  # bad examples contain errors
            with open(out, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["tool"], "convlint")
            self.assertEqual(len(data["reports"]), 7)

    def test_sarif(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out.sarif")
            rc = main(["lint", EX, "--format", "sarif", "--output", out])
            self.assertEqual(rc, 1)
            with open(out, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["version"], "2.1.0")
            self.assertTrue(data["runs"][0]["results"])

    def test_fail_on_never(self):
        rc = main(["lint", EX, "--fail-on", "never", "--quiet"])
        self.assertEqual(rc, 0)

    def test_good_example_clean(self):
        rc = main(["lint", os.path.join(EX, "good_first_call.txt"), "--quiet"])
        self.assertEqual(rc, 0)

    def test_disable_rule(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"disable": ["early-goodbye"]}, fh)
            cfg = fh.name
        rc = main(["lint", os.path.join(EX, "bad_early_goodbye.txt"),
                   "--config", cfg, "--quiet", "--fail-on", "warn"])
        self.assertEqual(rc, 0)
        os.unlink(cfg)


if __name__ == "__main__":
    unittest.main()
