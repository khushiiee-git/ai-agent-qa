"""Load rubrics and the failure taxonomy from YAML config.

Keeping these in config (not code) is deliberate: a new team can grade their
own agent by writing a rubric file, nothing in the engine changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

RUBRIC_DIR = Path(__file__).resolve().parent.parent / "rubrics"


@dataclass
class Criterion:
    id: str
    name: str
    weight: float
    description: str


@dataclass
class Rubric:
    name: str
    pass_at: float
    criteria: list[Criterion]

    @property
    def total_weight(self) -> float:
        return sum(c.weight for c in self.criteria)

    def weighted_score(self, scores: dict[str, int]) -> int:
        """Turn per-criterion 1-5 scores into a 0-100 weighted score."""
        num = 0.0
        den = 0.0
        for c in self.criteria:
            if c.id in scores and scores[c.id] is not None:
                num += (scores[c.id] / 5.0) * c.weight
                den += c.weight
        return round((num / den) * 100) if den else 0


@dataclass
class FailureTag:
    id: str
    name: str
    severity: str  # "critical" | "warning"
    description: str


def load_rubric(name: str = "sales_outbound") -> Rubric:
    path = RUBRIC_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text())
    criteria = [Criterion(**c) for c in data["criteria"]]
    return Rubric(name=data["name"], pass_at=data["pass_at"], criteria=criteria)


def load_failure_tags() -> dict[str, FailureTag]:
    path = RUBRIC_DIR / "failure_tags.yaml"
    data = yaml.safe_load(path.read_text())
    return {t["id"]: FailureTag(**t) for t in data["tags"]}
