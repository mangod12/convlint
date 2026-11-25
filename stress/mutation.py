"""Mutation testing for convlint rules.

Applies targeted single-token mutations to rule source, runs the unit tests
plus the labelled stress corpus against each mutant, and reports the kill
rate. A surviving mutant means the test corpus cannot tell correct code
from broken code at that spot.

Usage: python stress/mutation.py [--verbose]
"""
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
SRC = os.path.join(ROOT, "src")

# (file, original, mutated) - each must appear exactly once in the file
MUTATIONS = [
    ("rules/question_barrage.py", "if len(current) >= max_run:",
     "if len(current) > max_run:"),
    ("rules/enough_for_today.py", "if len(hits) >= warn_at:",
     "if len(hits) > warn_at:"),
    ("rules/enough_for_today.py", '"error" if len(hits) >= error_at else self.default_severity',
     '"error" if len(hits) > error_at else self.default_severity'),
    ("rules/early_goodbye.py", "t.t < max_dur - min_remaining_s \\",
     "t.t < max_dur + min_remaining_s \\"),
    ("rules/early_goodbye.py", "t.t < max_dur * end_frac:",
     "t.t <= max_dur * end_frac * 0.5:"),
    ("rules/early_goodbye.py", "i < n - 1 - end_turn_window:",
     "i < n - 1 + end_turn_window:"),
    ("rules/repeated_question.py", "sim_threshold = float(config.get(\"similarity\", 0.6))",
     "sim_threshold = float(config.get(\"similarity\", 0.99))"),
    ("rules/false_memory.py", "if len(novel) >= max(1, len(claim_words) // 2):",
     "if len(novel) >= max(1, len(claim_words)):"),
    ("rules/scripted_chain.py", "if len(hits) >= warn_at:",
     "if len(hits) > warn_at + 3:"),
    ("rules/premature_praise.py", "default_severity = \"warn\"",
     "default_severity = \"info\""),
    ("rules/boundary_value.py", "for m in _DIM.finditer(text):",
     "for m in list(_DIM.finditer(text))[::2]:"),
    ("hinglish.py", "return len(words) <= 2 and all(",
     "return len(words) <= 1 and all("),
]


def _clear_pycache():
    for dirpath, dirnames, _ in os.walk(SRC):
        for d in [d for d in dirnames if d == "__pycache__"]:
            import shutil
            shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)


def run_checks():
    _clear_pycache()
    r1 = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x"],
                        cwd=ROOT, capture_output=True)
    if r1.returncode != 0:
        return False, "pytest"
    r2 = subprocess.run([sys.executable, "stress/stress_extra.py", "labelled"],
                        cwd=ROOT, capture_output=True)
    if r2.returncode != 0:
        return False, "labelled"
    return True, ""


def main():
    verbose = "--verbose" in sys.argv
    killed, survived, invalid = [], [], []
    # sanity: unmutated tree must pass
    ok, stage = run_checks()
    if not ok:
        print(f"ABORT: unmutated tree fails {stage}")
        return 1
    for rel, orig, mut in MUTATIONS:
        path = os.path.join(SRC, "convlint", rel)
        text = open(path).read()
        if text.count(orig) != 1:
            invalid.append((rel, orig[:50]))
            continue
        try:
            open(path, "w").write(text.replace(orig, mut))
            ok, stage = run_checks()
            (killed if not ok else survived).append((rel, orig[:50], stage))
            if verbose or ok:
                print(f"  {'KILLED' if not ok else 'SURVIVED'} ({stage or '-'}) "
                      f"{rel}: {orig[:60]}")
        finally:
            open(path, "w").write(text)
            _clear_pycache()  # same-size restores can leave stale .pyc behind
    total = len(killed) + len(survived)
    print(f"mutations: {total} valid, {len(invalid)} not applicable")
    print(f"killed: {len(killed)}/{total} "
          f"({100.0 * len(killed) / max(total, 1):.0f}% kill rate)")
    for s in survived:
        print("  SURVIVOR:", s)
    for i in invalid:
        print("  INVALID (pattern not found/unambiguous):", i)
    return 0 if not survived else 1


if __name__ == "__main__":
    sys.exit(main())
