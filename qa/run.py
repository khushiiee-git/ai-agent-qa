"""Batch-grade a set of transcripts into the SQLite store.

    python -m qa.run                      # grade data/sample_transcripts.json
    python -m qa.run --rubric support     # use a different rubric
    python -m qa.run --file my_calls.json # grade your own transcripts

Without ANTHROPIC_API_KEY set, it loads the pre-computed grades in
data/sample_evaluations.json so you can see the whole pipeline run offline.
With the key set, it grades every transcript live through the Claude API.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import db
from .grader import grade, _finalise, DEFAULT_MODEL
from .rubric import load_rubric, load_failure_tags

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    ap = argparse.ArgumentParser(description="Grade agent call transcripts.")
    ap.add_argument("--file", default=str(DATA / "sample_transcripts.json"))
    ap.add_argument("--rubric", default="sales_outbound")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    rubric = load_rubric(args.rubric)
    tags = load_failure_tags()
    calls = json.loads(Path(args.file).read_text())

    conn = db.connect()
    db.init_db(conn)

    live = bool(os.environ.get("ANTHROPIC_API_KEY"))
    samples = {}
    if not live:
        samples = json.loads((DATA / "sample_evaluations.json").read_text())
        print("No ANTHROPIC_API_KEY found - using pre-computed sample grades.\n")
    else:
        print(f"Grading live with {args.model} on rubric '{rubric.name}'.\n")

    for call in calls:
        db.upsert_call(conn, call)
        if live:
            result = grade(call["transcript"], rubric, tags, model=args.model)
        else:
            raw = samples.get(call["id"])
            if not raw:
                print(f"  skip {call['id']} (no sample grade)")
                continue
            result = _finalise(raw, rubric, tags, model="sample")
        db.save_evaluation(conn, call["id"], result)
        mark = "PASS" if result["passed"] else "FAIL"
        print(f"  {call['id']:<8} {result['overall_score']:>3}  [{mark}]  {call['agent_version']}")

    conn.close()
    print("\nDone. Run `python -m qa.report` for the summary.")


if __name__ == "__main__":
    main()
