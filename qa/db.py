"""SQLite storage for calls, evaluations, and flags.

Schema notes (the design matters more than the SQL):

- `evaluation` is kept separate from `call` on purpose. One call can be graded
  many times - re-graded after we change the rubric, or graded by a different
  model - and we want to keep that history rather than overwrite it.
- scores and flags both reference the evaluation, not the call, for the same
  reason.
- `agent_version` lives on the call. That single column is what lets us ask
  "did prompt v2.4 actually score better than v2.3?" instead of guessing.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "qa.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS call (
    id            TEXT PRIMARY KEY,
    agent_version TEXT NOT NULL,
    lead          TEXT,
    outcome       TEXT,
    transcript    TEXT NOT NULL,   -- json: [{speaker, text}, ...]
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluation (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id        TEXT NOT NULL REFERENCES call(id),
    rubric         TEXT NOT NULL,
    model          TEXT NOT NULL,
    overall_score  INTEGER NOT NULL,
    passed         INTEGER NOT NULL,
    summary        TEXT,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS criterion_score (
    evaluation_id  INTEGER NOT NULL REFERENCES evaluation(id),
    criterion_id   TEXT NOT NULL,
    score          INTEGER NOT NULL,
    reasoning      TEXT,
    evidence_turns TEXT               -- json: [turn_index, ...]
);

CREATE TABLE IF NOT EXISTS flag (
    evaluation_id  INTEGER NOT NULL REFERENCES evaluation(id),
    tag            TEXT NOT NULL,
    severity       TEXT NOT NULL,
    turn_index     INTEGER,
    reasoning      TEXT
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_call(conn: sqlite3.Connection, call: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO call (id, agent_version, lead, outcome, transcript)
           VALUES (?, ?, ?, ?, ?)""",
        (
            call["id"],
            call["agent_version"],
            call.get("lead"),
            call.get("outcome"),
            json.dumps(call["transcript"]),
        ),
    )
    conn.commit()


def save_evaluation(conn: sqlite3.Connection, call_id: str, result: dict) -> int:
    """Persist one grading result (the dict the grader returns)."""
    cur = conn.execute(
        """INSERT INTO evaluation (call_id, rubric, model, overall_score, passed, summary)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            call_id,
            result["rubric"],
            result["model"],
            result["overall_score"],
            1 if result["passed"] else 0,
            result.get("summary"),
        ),
    )
    eval_id = cur.lastrowid

    for cs in result["criterion_scores"]:
        conn.execute(
            """INSERT INTO criterion_score
               (evaluation_id, criterion_id, score, reasoning, evidence_turns)
               VALUES (?, ?, ?, ?, ?)""",
            (
                eval_id,
                cs["criterion_id"],
                cs["score"],
                cs.get("reasoning"),
                json.dumps(cs.get("evidence_turns", [])),
            ),
        )

    for fl in result.get("flags", []):
        conn.execute(
            """INSERT INTO flag (evaluation_id, tag, severity, turn_index, reasoning)
               VALUES (?, ?, ?, ?, ?)""",
            (eval_id, fl["tag"], fl["severity"], fl.get("turn_index"), fl.get("reasoning")),
        )

    conn.commit()
    return eval_id
