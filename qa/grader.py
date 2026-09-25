"""The LLM-as-judge.

Given one transcript + a rubric + the failure taxonomy, ask Claude to return
a structured score. We force structured output with a tool definition rather
than parsing free text - the model has to return data shaped exactly like our
`criterion_score` / `flag` tables, so there's nothing to regex and nothing to
break at 2am.

Set ANTHROPIC_API_KEY to run against the real API. If the key is missing the
caller can fall back to the pre-graded sample data in data/ (see run.py), so
the repo is runnable without a key.
"""

from __future__ import annotations

import json
import os

from .rubric import Rubric, FailureTag

DEFAULT_MODEL = "claude-sonnet-5-5"  # good cost/quality point for grading


def _grading_tool(rubric: Rubric, tags: dict[str, FailureTag]) -> dict:
    """Build the tool schema the judge must fill in, from the active rubric."""
    criterion_ids = [c.id for c in rubric.criteria]
    tag_ids = list(tags.keys())
    return {
        "name": "record_evaluation",
        "description": "Record the quality evaluation of the agent's call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "2-3 sentences: how the call went and the single biggest issue.",
                },
                "criterion_scores": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "criterion_id": {"type": "string", "enum": criterion_ids},
                            "score": {"type": "integer", "minimum": 1, "maximum": 5},
                            "reasoning": {"type": "string"},
                            "evidence_turns": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "0-based turn indexes that justify the score.",
                            },
                        },
                        "required": ["criterion_id", "score", "reasoning"],
                    },
                },
                "flags": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "tag": {"type": "string", "enum": tag_ids},
                            "turn_index": {"type": "integer"},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["tag", "turn_index", "reasoning"],
                    },
                },
            },
            "required": ["summary", "criterion_scores"],
        },
    }


def _build_prompt(transcript: list[dict], rubric: Rubric, tags: dict[str, FailureTag]) -> str:
    crit_lines = "\n".join(
        f"- {c.id} ({c.name}, weight {c.weight}): {c.description.strip()}"
        for c in rubric.criteria
    )
    tag_lines = "\n".join(
        f"- {t.id} ({t.severity}): {t.description}" for t in tags.values()
    )
    turns = "\n".join(
        f"[{i}] {t['speaker'].upper()}: {t['text']}" for i, t in enumerate(transcript)
    )
    return f"""You are a strict QA reviewer for a conversational AI sales/support agent.
Grade the call below against the rubric. Score each criterion 1-5 and justify it
with specific turn numbers. Be critical: a made-up price or a missed disclosure
is a serious problem even if the call felt smooth.

RUBRIC: {rubric.name}
{crit_lines}

FAILURE TAGS you may flag (tie each to a turn):
{tag_lines}

TRANSCRIPT (turns are 0-indexed):
{turns}

Call record_evaluation with your assessment."""


def grade(
    transcript: list[dict],
    rubric: Rubric,
    tags: dict[str, FailureTag],
    model: str = DEFAULT_MODEL,
) -> dict:
    """Grade one transcript. Returns a dict ready for db.save_evaluation."""
    import anthropic  # imported here so the sample path works without the SDK

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    tool = _grading_tool(rubric, tags)

    msg = client.messages.create(
        model=model,
        max_tokens=1500,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_evaluation"},
        messages=[{"role": "user", "content": _build_prompt(transcript, rubric, tags)}],
    )

    data = next(b.input for b in msg.content if b.type == "tool_use")
    return _finalise(data, rubric, tags, model)


def _finalise(data: dict, rubric: Rubric, tags: dict[str, FailureTag], model: str) -> dict:
    """Compute the weighted score + attach severities. Shared with the sample path."""
    scores = {cs["criterion_id"]: cs["score"] for cs in data["criterion_scores"]}
    overall = rubric.weighted_score(scores)
    flags = [
        {
            "tag": f["tag"],
            "severity": tags[f["tag"]].severity,
            "turn_index": f.get("turn_index"),
            "reasoning": f.get("reasoning"),
        }
        for f in data.get("flags", [])
    ]
    return {
        "rubric": rubric.name,
        "model": model,
        "overall_score": overall,
        "passed": overall >= rubric.pass_at,
        "summary": data.get("summary"),
        "criterion_scores": data["criterion_scores"],
        "flags": flags,
    }
