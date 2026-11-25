# convlint

A deterministic linter for voice and chat agent transcripts. No LLM judge.

convlint reads real call or chat transcripts and flags the failure patterns
that actually lose users: the agent ending the call while time is left,
re-asking a question it already got an answer to, claiming to remember a
conversation that never happened, contradicting its own numbers, or getting
stuck in a scripted "now imagine X, say Y" drill loop.

Every rule is a deterministic check. Same transcript in, same findings out.
It runs offline, in CI, in milliseconds - and it speaks Hinglish: rules match
English, romanized Hindi, and Devanagari phrasing.

```text
$ convlint lint examples/bad_early_goodbye.txt
bad_early_goodbye: score 60/100 (C)  [error 2 · warn 0 · info 0]
  ERROR early-goodbye (turn 4): Agent farewell at 26s of a 600s call (more than 90s left).
        > Very good Rahul. That's all for today, goodbye! Try the app for more practice.
  ERROR early-goodbye (turn 6): Agent wrapped up with a farewell right after the user said
        time is left. Treat 'time left' as a cue to continue, not end.
        > You did great today! Phir milte hain, bye bye!
```

## Why not an LLM judge?

Most voice-agent eval tools simulate callers and grade with an LLM. That has
its place, but a judge that costs tokens, drifts between runs, and can't run
on every commit is not a regression gate. convlint is the other half of the
workflow: post-hoc checks on the transcripts your agent already produces,
cheap enough to run on every build, boring enough to trust.

- **Deterministic** - regexes, counts, and set logic. No model in the loop.
- **Fast** - thousands of transcripts per second on a laptop.
- **CI-friendly** - exit codes for pipelines, SARIF for GitHub code scanning.
- **Hinglish-aware** - built on production Hindi/English tutoring calls.

## Install

```bash
pip install convlint        # from PyPI (once published)
pip install -e .            # from a clone, zero runtime dependencies
```

Requires Python 3.9+. No dependencies.

## Quickstart

```bash
convlint lint transcripts/                  # lint a directory
convlint lint call.json --format json       # machine-readable output
convlint lint call.txt --fail-on warn       # stricter exit code
convlint lint calls/ --history calls/       # verify memory claims against past calls
convlint rules                              # list all rules
```

## Transcript formats

JSON (with optional metadata):

```json
{
  "meta": {"max_duration_s": 600},
  "turns": [
    {"role": "agent", "text": "Namaste! What do you do?", "t": 0},
    {"role": "user", "text": "I work in a shop.", "t": 5}
  ]
}
```

Plain text, with optional `[mm:ss]` timestamps:

```text
[00:00] Agent: Namaste! What do you do?
[00:05] User: I work in a shop.
```

JSONL and CSV work too. Roles accept `agent`/`ai`/`assistant`/`bot`/`tutor`
and `user`/`customer`/`learner`/`student`/`caller`. Timestamps and
`max_duration_s` unlock the timing-based checks (early goodbyes).

## Rules

| Rule | Severity | What it flags |
|---|---|---|
| `early-goodbye` | error | Agent farewell while call time is left, or right after the user says time remains ("abhi toh time hai"). |
| `enough-for-today-loop` | warn, error at 3+ | Repeated "is that enough for today? / shall we stop?" check-outs that push the learner to hang up. |
| `repeated-question` | warn, error on correction | Re-asking a question the user already answered; any question that draws "maine toh bataya". |
| `false-memory` | warn, error when disproved | "Last time you told me X" claims - error when the user says it's their first call or past sessions don't contain the claim. |
| `boundary-value` | error | Numeric facts (ages, limits, prices) the agent contradicts or re-asserts after the user disputes them. |
| `scripted-chain` | warn, error at 8+ | Long chains of "now imagine X, say Y" drills. |
| `question-barrage` | warn | Runs of agent questions against a passive learner ("haan", "pata nahi"). |
| `premature-praise` | warn | Farewell-sounding praise ("today you did great") in the middle of a call. |

### Configure

Drop a `.convlint.json` in your repo:

```json
{
  "disable": ["premature-praise"],
  "severity_overrides": {"question-barrage": "error"},
  "thresholds": {
    "scripted-chain": {"warn_at": 4, "error_at": 7},
    "early-goodbye": {"min_remaining_s": 120, "end_fraction": 0.85},
    "enough-for-today-loop": {"warn_at": 2, "error_at": 3},
    "question-barrage": {"max_consecutive": 4}
  }
}
```

## CI

```yaml
- run: pip install convlint
- run: convlint lint transcripts/ --format sarif --output convlint.sarif --fail-on error
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: convlint.sarif
```

`convlint lint` exits 1 when findings at or above `--fail-on` severity exist.

## Scoring

Each transcript scores 100 minus severity weights (error 20, warn 5), graded
A (90+) to F (<40). Scores are for triage: sort your worst calls first. The
findings, with turn numbers and evidence snippets, are the real output.

## Where it came from

convlint's rules are failure modes observed on a production voice agent for
English learners in India: an agent that ended calls early and lost the
learner mid-session, an eligibility check that said 18-70 and then denied a
71-year-old for being over 60, a returning-learner flow that invented shared
history. The example transcripts in `examples/` are synthetic; no customer
data is in this repo.

## Limitations

- Rules are heuristic. Expect both false positives and false negatives, and
  tune thresholds per product. A finding starts a review; it is not proof.
- `false-memory` can only disprove claims when you pass `--history`; without
  history it flags every claim as unverifiable.
- Timing rules need timestamps or `max_duration_s` in the transcript.
- convlint checks what the transcript shows. It cannot hear audio quality,
  latency, or interruptions that never made it to the transcript.

## Roadmap

- More input adapters (Retell, Vapi, Deepgram export formats)
- Rule packs per use case (tutoring, collections, support)
- Trend reports across runs

## License

MIT
