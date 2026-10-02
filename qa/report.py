"""Print a QA summary from the graded calls in SQLite.

    python -m qa.report

Shows overall quality, pass rate, per-criterion averages, the top failure
modes, and - the point of the whole thing - a before/after comparison across
agent versions.
"""

from __future__ import annotations

from collections import defaultdict

from . import db
from .rubric import load_rubric, load_failure_tags


def _bar(pct: float, width: int = 20) -> str:
    filled = round(pct / 100 * width)
    return "#" * filled + "." * (width - filled)


def main() -> None:
    rubric = load_rubric()
    tags = load_failure_tags()
    conn = db.connect()

    rows = conn.execute(
        """SELECT e.overall_score, e.passed, c.agent_version
           FROM evaluation e JOIN call c ON c.id = e.call_id"""
    ).fetchall()

    if not rows:
        print("No evaluations yet. Run `python -m qa.run` first.")
        return

    n = len(rows)
    avg = sum(r["overall_score"] for r in rows) / n
    pass_rate = sum(r["passed"] for r in rows) / n * 100

    print("=" * 52)
    print(f"  AGENT QA REPORT  -  {rubric.name}")
    print("=" * 52)
    print(f"  Calls graded      {n}")
    print(f"  Avg quality score {avg:.0f} / 100")
    print(f"  Pass rate (>={rubric.pass_at:.0f}) {pass_rate:.0f}%")

    # per-criterion averages
    print("\n  Score by criterion")
    cs = conn.execute("SELECT criterion_id, AVG(score) a FROM criterion_score GROUP BY criterion_id").fetchall()
    cmap = {r["criterion_id"]: r["a"] for r in cs}
    for c in rubric.criteria:
        a = cmap.get(c.id, 0)
        print(f"    {c.name:<22} {a:.1f}/5  {_bar(a / 5 * 100)}")

    # failure modes
    print("\n  Top failure modes")
    fl = conn.execute("SELECT tag, COUNT(*) n FROM flag GROUP BY tag ORDER BY n DESC").fetchall()
    if fl:
        for r in fl:
            meta = tags.get(r["tag"])
            label = meta.name if meta else r["tag"]
            sev = meta.severity.upper() if meta else ""
            print(f"    {label:<28} {r['n']:>2}  [{sev}]")
    else:
        print("    (none flagged)")

    # version comparison - the headline
    print("\n  Quality by agent version")
    byver = defaultdict(list)
    for r in rows:
        byver[r["agent_version"]].append(r["overall_score"])
    for ver in sorted(byver):
        scores = byver[ver]
        a = sum(scores) / len(scores)
        print(f"    {ver:<8} {a:.0f}/100  (n={len(scores)})  {_bar(a)}")
    if len(byver) >= 2:
        versions = sorted(byver)
        lo = sum(byver[versions[0]]) / len(byver[versions[0]])
        hi = sum(byver[versions[-1]]) / len(byver[versions[-1]])
        print(f"\n  -> {versions[0]} to {versions[-1]}: {hi - lo:+.0f} points")
    print("=" * 52)

    conn.close()


if __name__ == "__main__":
    main()
