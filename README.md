# Agent QA

Automated quality grading for conversational AI agents.

When a team swaps a human call centre for an AI voice or chat agent, the QA
function usually quietly disappears. Human agents got call audits against a
scorecard; the AI agent ships and gets watched only by conversion rate. That's
a bad trade, because conversion tells you *that* a week went badly, not *why* a
call went badly.

This is a small tool that grades every agent transcript against a rubric using
an LLM as the judge, flags the specific turns that went wrong, and tracks
whether quality actually improved when the prompt changed.

I built it off the back of working on an AI outbound-sales agent, where exactly
this gap was the problem: we could see bookings go up or down but couldn't say
which prompt change caused it, or catch the agent inventing a discount until a
customer mentioned it.

---

## What it does

- **Grades 100% of calls, not a 2% sample.** The transcripts are already text,
  so grading is cents per call instead of an analyst's afternoon.
- **Scores against a rubric you define** (criteria + weights) and produces a
  0–100 weighted score per call.
- **Flags specific failures on specific turns** — a hallucinated price, a
  missed compliance disclosure, giving up after one objection — using a
  severity-tagged taxonomy.
- **Compares agent versions.** Every call is stored against the prompt version
  that produced it, so "did v2.4 beat v2.3?" is a number, not a hunch.

There's also an [interactive dashboard demo](https://claude.ai/artifact/FHg8CTLoByNaXPuNkn8iYB)
that shows the output on a set of synthetic calls.

## Why it's built the way it is

A few decisions worth calling out (longer notes in [`docs/DECISIONS.md`](docs/DECISIONS.md)):

- **The rubric is config, not code.** Criteria, weights, and the failure
  taxonomy live in `rubrics/*.yaml`. A support team can grade their own agent
  by writing a rubric file — the engine doesn't change. `rubrics/support.yaml`
  is there to prove the sales logic isn't hardcoded.
- **Structured output via tool use.** The judge is forced to return data shaped
  exactly like the database tables, so there's no fragile text parsing.
- **Evaluations are stored separately from calls**, so a call can be re-graded
  (new rubric, new model) without losing the old result.

## Running it

It runs end-to-end **without an API key** on pre-computed sample grades, so you
can see the whole pipeline immediately:

```bash
pip install -r requirements.txt

python -m qa.run       # grade the sample transcripts into SQLite
python -m qa.report    # print the QA summary
```

Expected report (abridged):

```
  AGENT QA REPORT  -  Outbound Sales (real estate)
  Calls graded      6
  Avg quality score 80 / 100
  Pass rate (>=70) 83%

  Top failure modes
    Robotic / unnatural           1  [WARNING]
    Hallucinated fact or price    1  [CRITICAL]
    Gave up after one objection   1  [WARNING]
    Compliance / disclosure miss  1  [CRITICAL]

  Quality by agent version
    v2.3   72/100  (n=3)
    v2.4   87/100  (n=3)
    -> v2.3 to v2.4: +16 points
```

To grade live through the Claude API, set a key and run the same commands:

```bash
cp .env.example .env     # add your key, or just export it
export ANTHROPIC_API_KEY=sk-ant-...
python -m qa.run
```

Grade your own calls with `python -m qa.run --file your_calls.json`, or a
different rubric with `--rubric support`.

## Layout

```
rubrics/        rubric + failure-taxonomy config (YAML)
qa/
  rubric.py     load rubrics, compute weighted scores
  db.py         SQLite schema + storage
  grader.py     the LLM-as-judge (structured output)
  run.py        batch runner
  report.py     CLI summary + version comparison
  generate_samples.py   synthetic transcripts with planted defects
data/           sample transcripts + pre-computed grades
docs/           design notes
```

## What I'd do next

- **Calibrate the judge.** `generate_samples.py` plants a known defect in each
  synthetic call; the next step is measuring how often the grader catches it,
  to put a confidence number on the scores before trusting them. An LLM judge
  that nobody audits is just a different blind spot.
- Correlate QA score against actual outcome (does a high score predict a
  booking?), which the schema already supports via the `outcome` field.
- A proper web dashboard instead of a CLI report.

## Note on the data

Every transcript, lead, and score in this repo is **synthetic**, generated for
demonstration. No real customer or company data is included.
