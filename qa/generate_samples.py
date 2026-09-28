"""Generate synthetic call transcripts for testing the grader.

Why synthetic: (1) real call data is sensitive and can't live in a public repo,
and (2) planting known failures lets us check whether the grader actually
catches them - a basic sanity check on the judge itself.

    python -m qa.generate_samples --n 20 --out data/generated.json

Needs ANTHROPIC_API_KEY. Each call is generated with a hidden "defect" label
(clean / hallucination / compliance / gave_up / robotic); you can later compare
the grader's flags against that label to estimate how well the judge agrees
with ground truth.
"""

from __future__ import annotations

import argparse
import json
import os
import random

DEFECTS = ["clean", "clean", "hallucination", "compliance", "gave_up", "robotic"]

GEN_PROMPT = """Write a short, realistic transcript (8-12 turns) of an outbound
real-estate sales call by an AI agent named Radhika to a prospective buyer in
Hyderabad. Alternate "agent" and "customer".

Inject this specific flaw: {defect}
  - clean: a solid call, no issues.
  - hallucination: the agent invents a discount or price not in approved info.
  - compliance: the agent skips a required disclosure (e.g. NRI payment rules).
  - gave_up: the agent abandons the call after one objection.
  - robotic: the agent delivers a long scripted block ignoring the customer.

Return ONLY JSON: {{"transcript": [{{"speaker": "agent"|"customer", "text": "..."}}]}}"""


def generate(n: int) -> list[dict]:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    out = []
    for i in range(n):
        defect = random.choice(DEFECTS)
        msg = client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=1200,
            messages=[{"role": "user", "content": GEN_PROMPT.format(defect=defect)}],
        )
        text = msg.content[0].text
        text = text[text.find("{"): text.rfind("}") + 1]
        data = json.loads(text)
        out.append(
            {
                "id": f"G-{1000 + i}",
                "agent_version": random.choice(["v2.3", "v2.4"]),
                "lead": "Synthetic lead",
                "outcome": "unknown",
                "planted_defect": defect,  # ground-truth label for judge validation
                "transcript": data["transcript"],
            }
        )
        print(f"  generated G-{1000 + i} ({defect})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default="data/generated.json")
    args = ap.parse_args()
    calls = generate(args.n)
    with open(args.out, "w") as f:
        json.dump(calls, f, indent=2)
    print(f"\nWrote {len(calls)} calls to {args.out}")


if __name__ == "__main__":
    main()
