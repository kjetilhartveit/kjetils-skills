"""Tabulate the scores of runs and corpus pages side by side, as a markdown table.

Usage:
    python compare.py [runs/<label> ...] [--baseline LABEL]      # default: every label under runs/

One row per run folder that has a score.json (run score.py first), plus a mean row per label with more than one
run. With --baseline, each mean row says whether the candidate passes the quality gate (quality within 3 points
of the baseline mean, or higher): a faster candidate that fails the gate is not an improvement.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

LOOP_DIR = Path(__file__).resolve().parents[1]
COLUMNS = ("overall", "quality", "checks", "judge", "speed", "economy", "out_tok", "wall_s", "turns", "cost", "words", "chapters")
QUALITY_GATE_TOLERANCE = 3


def row_of(score_path: Path) -> dict:
    score = json.loads(score_path.read_text(encoding="utf-8"))
    run = score.get("run") or {}
    measures = score.get("page_measures") or {}
    judge = score.get("judge") or {}
    return {
        "name": score_path.parent.name, "label": score_path.parent.parent.name,
        "overall": score["overall"], "quality": score["quality"],
        "checks": score["checks"]["score"], "judge": judge.get("score"),
        "speed": score.get("speed"), "economy": score.get("economy"),
        "out_tok": run.get("output_tokens_total"), "wall_s": run.get("wall_s"), "turns": run.get("num_turns"),
        "cost": run.get("total_cost_usd"), "words": measures.get("visible_words"),
        "chapters": len(measures.get("sections") or []),
    }


def fmt(value) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:.2f}" if value < 10 else f"{value:.1f}"
    return str(value)


def mean_row(label: str, rows: list[dict]) -> dict:
    out = {"name": f"mean of {len(rows)}", "label": label}
    for column in COLUMNS:
        values = [r[column] for r in rows if r[column] is not None]
        out[column] = round(mean(values), 1) if values else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("targets", nargs="*", type=Path)
    parser.add_argument("--baseline", help="label whose mean quality sets the quality gate")
    args = parser.parse_args()
    targets = args.targets or sorted(p for p in (LOOP_DIR / "runs").iterdir() if p.is_dir())

    rows_by_label: dict[str, list[dict]] = {}
    for target in targets:
        for score_path in sorted(target.glob("*/score.json")) or sorted(target.glob("score.json")):
            row = row_of(score_path)
            rows_by_label.setdefault(row["label"], []).append(row)
    means = {label: mean_row(label, rows) for label, rows in rows_by_label.items()}
    gate = means[args.baseline]["quality"] if args.baseline in means else None

    print("| label | run | " + " | ".join(COLUMNS) + (" | gate |" if gate is not None else " |"))
    print("|---|---|" + "|".join("---:" for _ in COLUMNS) + ("|---|" if gate is not None else "|"))
    for label, rows in rows_by_label.items():
        for row in rows:
            print(f"| {label} | {row['name']} | " + " | ".join(fmt(row[c]) for c in COLUMNS) + (" | |" if gate is not None else " |"))
        if len(rows) > 1 or gate is not None:
            m = means[label]
            verdict = ""
            if gate is not None and m["quality"] is not None:
                verdict = " | " + ("pass" if m["quality"] >= gate - QUALITY_GATE_TOLERANCE else "FAIL") + " |"
            elif gate is not None:
                verdict = " | – |"
            print(f"| **{label}** | **{m['name']}** | " + " | ".join(f"**{fmt(m[c])}**" for c in COLUMNS) + (verdict or " |"))


if __name__ == "__main__":
    main()
