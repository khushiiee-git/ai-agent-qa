# Design decisions

Short notes on the choices that weren't obvious, and why I made them. Mostly
here so I remember my own reasoning later.

### Why grade transcripts at all instead of just watching conversion?

Conversion tells you *that* something is wrong, weeks later, and never *why*.
A single number can't separate "the agent is quoting a fake discount" from
"the leads this week were just colder." Grading every transcript gives a
leading signal and points at the specific turn that went wrong.

### Why the rubric lives in YAML, not in the code

The first version had the criteria hardcoded. The moment I imagined a support
team wanting to use this, that felt wrong - they shouldn't have to edit Python
to change what "good" means. So the rubric (criteria, weights, pass threshold)
and the failure taxonomy are config. The engine just reads them. `support.yaml`
exists only to prove the sales logic isn't baked in.

### Why force structured output with a tool instead of parsing text

Early on I asked the model to "return JSON" in the prompt and it mostly worked -
until it wrapped the JSON in prose, or added a trailing comment, and the parse
blew up. Defining a tool with an input schema makes the model return data
shaped exactly like the database tables. Fewer moving parts, nothing to regex.

### Why `evaluation` is a separate table from `call`

I want to re-grade. When the rubric changes, or a newer model comes out, I
should be able to grade the same call again and keep both results to compare.
If scores lived on the call row I'd be overwriting history every time.

### Why `agent_version` is on every call

This is the column that earns its place. Without it, "did the new prompt
actually help?" is a vibe. With it, it's a GROUP BY. The before/after number in
the report is the thing I'd actually show a stakeholder.

### Known limitation: who grades the grader?

An LLM judge can be wrong or drift. I haven't fully solved this. The
`generate_samples.py` script plants a known defect in each synthetic call, so
the next step is to measure how often the grader's flags match that ground-truth
label - a cheap proxy for judge accuracy before trusting the scores. That
calibration step is on the roadmap, not done yet.
