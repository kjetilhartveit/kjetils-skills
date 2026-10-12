"""Score one explainer run (or a bare page) as one comparable number plus a breakdown. Rubric: ../scoring.md.

Usage:
    python score.py <run-dir>                       # run folder with out/index.html and result.json
    python score.py <page.html> [--out DIR]         # a bare page (e.g. the corpus); no speed part
    options: --no-judge (deterministic parts only), --rejudge (ignore the cached judge.json),
             --judge-model opus, --judge-runs 1 (average several judgements), --remeasure

    quality  Q = 0.35 * checks + 0.65 * judge                  checks: facts 40, layout 30, structure 30
    speed    E = log-linear output tokens, wall time, turns, cost, context (runs only)
    economy  S = mean(words band, bytes, chapters)
    overall    = 0.60 Q + 0.25 E * min(1, Q / 75) + 0.15 S      (runs)
               = (0.60 Q + 0.15 S) / 0.75                      (bare pages)

Writes score.json (and judge.json, the cached verdict) next to measures.json. The judge is blind: it gets a
temporary folder with the facts file, the rendered page text (every toggle and hidden panel opened) and the
screenshots under neutral names, never the run's label, path, transcript or skills.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from statistics import mean

TOOLS_DIR = Path(__file__).resolve().parent
LOOP_DIR = TOOLS_DIR.parent
FACTS_FILE = LOOP_DIR / "inputs" / "facts-oxlint.md"
sys.path.insert(0, str(TOOLS_DIR))

# What an honest answer to this question has to contain, as regexes over the rendered page text (any alternative
# counts). Specific to the oxlint/Biome task: a new task needs its own anchors.
KEY_FACTS = {
    "names the Oxc formatter oxfmt": r"\boxfmt\b",
    "oxlint migrator keeps 263 rules": r"\b263\b",
    "rule base 276 or 295": r"\b(276|295)\b",
    "Biome keeps 163 (or 152) rules / about half": r"\b(163|152)\b|\b(55|45)\s?%|about half|roughly half|almost half",
    "lint time compared in seconds": r"\b(44(\.0)?|47(\.3)?|29\.4|39\.4)\s?s\b[\s\S]{0,400}?\b\d(\.\d)?\s?s\b",
    "react-x typed rule crashes / must be dropped": r"react-x|crash|190 files|185 files|leaked-conditional",
    "type-aware no-unsafe rules via tsgolint": r"no-unsafe|type-aware|tsgolint",
    "testing-library plugin": r"testing-library",
    "the two local custom rules": r"local/|custom rules?|local rules?|eslint-rules",
    "Biome ignores eslint-disable comments": r"biome-ignore|ignores? (the |all |every )?(~?\d+ )?eslint-disable",
    "low-risk path: oxfmt first, keep ESLint": r"oxfmt (only|first)|formatter first|keep(ing)? eslint|eslint stays|format(ter)? half first",
    "formatting is not enforced today / drift": r"not enforced|isn.t enforced|drift|nothing checks|no format(ting)? check|unformatted|14[69] files",
    "line endings / .gitattributes": r"\.gitattributes|CRLF|line endings?",
    "JS plugins are alpha (risk)": r"\balpha\b",
    "effort sized per option": r"\b\d(\s?[–-]\s?\d)?\s?(days?|hours?)\b|half a day|half-day",
    "lost no-restricted-syntax path checks": r"no-restricted-syntax|path checks?|vi\.mock",
    "what would change the recommendation": r"would change|would flip|what changes the|revisit (if|when)|switch (to biome )?(if|when)|reconsider",
}
SOURCE_LINK = r'href="https?://(www\.)?(oxc\.rs|biomejs\.dev|github\.com/(oxc-project|biomejs))'
# Universal claims the facts contradict (one rule crashes, path checks are lost, Biome drops 132 rules).
OVERCLAIMS = {
    "every/all rules carry over": r"(?<!nearly )(?<!almost )(?<!not )\b(every|all)( of the| \d+)? (eslint |lint )?rules? (carr(y|ies)|are kept|is kept|survive|migrate)",
    "every plugin family carries over": r"\b(every|all)( \d+)? plugin famil(y|ies)[^.]{0,40}carr",
    "drop-in / no rules lost": r"drop-in replacement|no rules? (are |is |get )?lost|without losing (a|any) rules?|zero (rule|config) changes|100 ?% of (the |our )?rules",
}
OVERCLAIM_PENALTY, OVERCLAIM_CAP = 5, 15

JUDGE_CRITERIA = {  # name: (weight out of 100, what 10 means)
    "headline": (10, "The overview headline and lede state the answer AND the main trade-off, with the key numbers, before any scrolling; the lede and key line add numbers rather than repeating the headline."),
    "accuracy": (15, "Substance agrees with facts.md: what works, breaks, is kept, lost or recommended. Overclaims and universals ('every rule carries over', 'runs our rules as they are'), contradictions between parts of the page, invented findings and wrong tool names (there is no 'oxprettier') are major faults. A page that measured on its own may have other timings if it states its method."),
    "evidence": (10, "Numbers come with their method and conditions (what was run, single runs, cache state, versions), sources are linked or named, and the limits of the evidence are stated instead of hidden."),
    "story": (15, "The story chapter has an arc (today -> what goes wrong -> the change -> result -> consequences) in short steps, with ONE concrete, to-scale graphic that evolves step by step (check the story screenshots), rather than a static dashboard, a table that lights up, or unrelated pictures."),
    "decision": (15, "Decision support: 2-3 options including a cautious one, a clear recommendation, effort per option, risks with concrete fixes, what has to be decided, and what would change the recommendation."),
    "concision": (10, "Concise but complete: the reader gets the answer fast and can find the details; each key number has one home; no padding, no chapters that restate each other. Penalise thin pages that leave out facts a decision needs just as much as bloated ones."),
    "clarity": (10, "A reader new to these tools can follow: jargon (nursery, tsgolint, GritQL, JS plugins, type-aware) is explained where it first appears, and brief real code or config makes a claim concrete where that helps."),
    "phone": (8, "From the phone screenshots: text and graphic labels legible at 390 px, nothing cut off or overflowing sideways, and mid-story the graphic is still visible with its step (pinned, taking well under half the screen) rather than lost above or below the steps."),
    "desktop": (7, "From the desktop screenshots: side panels level with their first text box, no large empty areas or stranded steps, nothing cut off, finished in both dark and light."),
}
JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        **{
            name: {
                "type": "object",
                "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 10}, "why": {"type": "string"}},
                "required": ["score", "why"],
            }
            for name in JUDGE_CRITERIA
        },
        "factual_errors": {"type": "array", "items": {"type": "string"}},
        "verdict": {"type": "string"},
    },
    "required": [*JUDGE_CRITERIA, "factual_errors", "verdict"],
}
JUDGE_PROMPT = """You are grading ONE explainer web page, blind: you do not know who or what produced it and must not guess.
The page answers this request from a developer about their repository:

  "We're looking to move away from eslint and prettier to oxlint and oxprettier or Biome. Can you help me explore this? Explain visually"

Files in the current folder (read them all with the Read tool before grading):
- facts.md: the ground truth. Everything the page claims should be supported by it.
- page.txt: the page's rendered text with every toggle opened; text inside graphics and in panels that only show
  when clicked is listed at the end.
- shots/*.png: desktop-dark.png and desktop-light.png (first screen), phone-dark.png and phone-light.png (first screen
  at 390 px), desktop-dark-full.png (whole page, scaled down), story-desktop-step*.png (the story chapter at its first,
  middle and last step) and story-phone-step*.png (the story's middle step on a phone). Some may be missing if the
  page has no story.

A great page, for reference: states the answer and trade-off in the headline; one to-scale hero; a short story with
one evolving graphic; a decision chapter with a recommended option, a cautious option, effort, risks with fixes and
what would change the decision; about 1,000-1,800 words; each key number has one home; jargon explained; legible
on a phone. A page that is short because it leaves out the evidence or the decision support is NOT good; a page
that is long because it repeats itself or pads chapters is not good either.

Score each criterion 0-10 (10 = as good as it reasonably gets, 5 = mediocre, 0 = missing or wrong), using the whole
scale, and say what on the page drove the score:
{criteria}

Also list every factual error or overclaim you find (quote the page, cite the fact it contradicts), and give a
two-sentence verdict: what the page does well and its biggest weakness. Be strict and consistent; do not reward
length for its own sake."""

SPEED_ANCHORS = {  # value in result.json: (weight, value scoring 100, value scoring 0); log-linear in between
    "output_tokens_total": (0.45, 8_000, 100_000),
    "wall_s": (0.20, 60, 1_800),
    "num_turns": (0.10, 6, 120),
    "total_cost_usd": (0.10, 0.2, 12.0),
    "input_tokens_total": (0.15, 300_000, 20_000_000),
}
WORD_BAND = {"min": 1_000, "max": 1_800, "thin": 400, "bloated": 5_000}
BYTES_ANCHOR = (100_000, 320_000)
CHAPTER_SCORES = {1: 40, 2: 90, 3: 100, 4: 100, 5: 70, 6: 40}
QUALITY_GATE = 75  # speed only counts in full once quality reaches this


def clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def log_linear(value: float | None, best: float, worst: float) -> float | None:
    """100 at or below `best`, 0 at or above `worst`, log-linear in between."""
    if value is None or value <= 0:
        return None
    if value <= best:
        return 100.0
    if value >= worst:
        return 0.0
    return 100.0 * (math.log(worst) - math.log(value)) / (math.log(worst) - math.log(best))


def band(value: float, lo: float, hi: float, floor_lo: float, floor_hi: float) -> float:
    """100 inside [lo, hi], falling linearly to 0 at floor_lo / floor_hi."""
    if lo <= value <= hi:
        return 100.0
    if value < lo:
        return clamp(100.0 * (value - floor_lo) / (lo - floor_lo))
    return clamp(100.0 * (floor_hi - value) / (floor_hi - hi))


def check_facts(text: str, page_html: str) -> dict:
    flat = re.sub(r"\s+", " ", text)
    found = {name: bool(re.search(pattern, flat, re.I)) for name, pattern in KEY_FACTS.items()}
    found["links to oxc.rs / biomejs.dev sources"] = bool(re.search(SOURCE_LINK, page_html, re.I))
    overclaims = [
        f"{name}: ...{flat[max(0, m.start() - 50):m.end() + 30]}..."
        for name, pattern in OVERCLAIMS.items()
        for m in re.finditer(pattern, flat, re.I)
    ]
    points = 40 * sum(found.values()) / len(found) - min(OVERCLAIM_CAP, OVERCLAIM_PENALTY * len(overclaims))
    return {"points": round(max(0.0, points), 1), "max": 40, "found": found, "overclaims": overclaims}


def check_layout(report: dict) -> dict:
    penalties: list[tuple[float, str]] = []
    for key, view in report.items():
        phone = key.startswith("phone")
        if view.get("horizontalOverflow"):
            penalties.append((5 if phone else 3, f"{key}: page {view['pageWidth']}px wide on {view['viewportWidth']}px: {', '.join(view.get('overflowingElements', [])[:3])}"))
        if view.get("stickyPanelsCutOff"):
            penalties.append((2.5, f"{key}: {view['stickyPanelsCutOff']} sticky panel(s) cut off"))
        if view.get("codeBlocksScrollingSideways"):
            penalties.append((min(2.5, 0.5 * view["codeBlocksScrollingSideways"]), f"{key}: {view['codeBlocksScrollingSideways']} code block(s) scroll sideways"))
        if view.get("errors"):
            penalties.append((2.5, f"{key}: {len(view['errors'])} console error(s)"))
        if phone and view.get("pinnedPanelViewportShare", 0) > 0.6:
            penalties.append((3, f"{key}: pinned panel takes {round(view['pinnedPanelViewportShare'] * 100)}% of the viewport"))
        if phone and view.get("svgTexts"):
            share = view["svgTextsTooSmall"] / view["svgTexts"]
            if share > 0.1:
                penalties.append((round(4 * share, 1), f"{key}: {view['svgTextsTooSmall']}/{view['svgTexts']} SVG labels under 9px"))
        for group in view.get("steps", []):
            bad = max(group["panelOutOfView"], group["stepCovered"])
            if bad:
                penalties.append((round(4 * bad / group["steps"], 1), f"{key}: {group['section']}: panel out of view or covering the step on {bad}/{group['steps']} steps"))
    total = sum(points for points, _ in penalties)
    return {"points": round(max(0.0, 30 - total), 1), "max": 30, "problems": [f"-{p} {why}" for p, why in penalties]}


def check_structure(measures: dict, report: dict, page_html: str) -> dict:
    chapters = len(measures["sections"])
    words = measures["visible_words"]
    story_steps = sum(group["steps"] for group in report["desktop-dark"].get("steps", []) if group["section"] == "story")
    checks = {
        "at most 4 chapters": 8 if chapters <= 4 else 4 if chapters == 5 else 0,
        "story with 4-9 steps": 5 if 4 <= story_steps <= 9 else 0,
        "decision chapter": 5 if "decide" in measures["sections"] else 0,
        "not thin (>= 900 words)": 4 if words >= 900 else round(4 * max(0, words - 500) / 400, 1),
        "no literal colours in fragments": max(0, 4 - measures["literal_colours_in_fragment_styles"]),
        "toggles name their contents": 4 if measures["toggles"] == 0 or "ev-more-what" in page_html else 0,
    }
    return {"points": round(sum(checks.values()), 1), "max": 30, "checks": checks}


def economy(measures: dict) -> dict:
    words = measures["visible_words"]
    parts = {
        "words": round(band(words, WORD_BAND["min"], WORD_BAND["max"], WORD_BAND["thin"], WORD_BAND["bloated"]), 1),
        "bytes": round(log_linear(measures["bytes"], *BYTES_ANCHOR) or 0.0, 1),
        "chapters": CHAPTER_SCORES.get(len(measures["sections"]), 10),
    }
    return {"score": round(sum(parts.values()) / len(parts), 1), "parts": parts}


def speed(result: dict) -> dict:
    parts, total, weight_sum = {}, 0.0, 0.0
    for key, (weight, best, worst) in SPEED_ANCHORS.items():
        value = result.get(key)
        part = log_linear(float(value) if value is not None else None, best, worst)
        parts[key] = {"value": value, "score": None if part is None else round(part, 1), "weight": weight}
        if part is not None:
            total += weight * part
            weight_sum += weight
    return {"score": round(total / weight_sum, 1) if weight_sum else None, "parts": parts}


def judge_once(shots_dir: Path, model: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="evjudge-") as blind:
        blind_dir = Path(blind)
        shutil.copy(FACTS_FILE, blind_dir / "facts.md")
        shutil.copy(shots_dir / "page.txt", blind_dir / "page.txt")
        (blind_dir / "shots").mkdir()
        for png in shots_dir.glob("*.png"):
            if png.name != "desktop-light-full.png":
                shutil.copy(png, blind_dir / "shots" / png.name)
        criteria = "\n".join(f"- {name}: {text}" for name, (_, text) in JUDGE_CRITERIA.items())
        command = [
            shutil.which("claude") or "claude", "-p", "--model", model, "--output-format", "json",
            "--tools", "Read", "--allowedTools", "Read", "--strict-mcp-config", "--disable-slash-commands",
            "--no-session-persistence", "--max-turns", "30", "--max-budget-usd", "6",
            "--json-schema", json.dumps(JUDGE_SCHEMA),
        ]
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        env["PYTHONUTF8"] = "1"
        completed = subprocess.run(
            command, cwd=blind_dir, env=env, input=JUDGE_PROMPT.format(criteria=criteria), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=900,
        )
    raw = completed.stdout.strip()
    try:
        result = json.loads(raw[raw.index("{"):])
        verdict = result["structured_output"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        sys.exit(f"judge failed (exit {completed.returncode}):\n{raw[-2000:]}\n{completed.stderr[-2000:]}")
    weighted = sum(weight * verdict[name]["score"] / 10 for name, (weight, _) in JUDGE_CRITERIA.items())
    return {"score": round(weighted, 1), "cost_usd": result.get("total_cost_usd"), "verdict": verdict}


def run_judge(shots_dir: Path, model: str, runs: int) -> dict:
    judgements = [judge_once(shots_dir, model) for _ in range(runs)]
    items = {name: round(mean(j["verdict"][name]["score"] for j in judgements), 1) for name in JUDGE_CRITERIA}
    return {
        "score": round(mean(j["score"] for j in judgements), 1),
        "model": model,
        "runs": runs,
        "cost_usd": round(sum(j["cost_usd"] or 0 for j in judgements), 3),
        "items": items,
        "reasons": {name: judgements[0]["verdict"][name]["why"] for name in JUDGE_CRITERIA},
        "factual_errors": judgements[0]["verdict"]["factual_errors"],
        "verdict": judgements[0]["verdict"]["verdict"],
        "scores_per_run": [j["score"] for j in judgements],
    }


def score(page: Path, out_dir: Path, result: dict | None, args: argparse.Namespace) -> dict:
    measures_file, shots_dir = out_dir / "measures.json", out_dir / "shots"
    if args.remeasure or not measures_file.exists() or not (shots_dir / "page.txt").exists():
        from measure import measure_page

        measure_page(page, out_dir)
    measures = json.loads(measures_file.read_text(encoding="utf-8"))
    report = json.loads((shots_dir / "report.json").read_text(encoding="utf-8"))
    page_html = page.read_text(encoding="utf-8", errors="replace")
    text = (shots_dir / "page.txt").read_text(encoding="utf-8")

    checks = {"facts": check_facts(text, page_html), "layout": check_layout(report), "structure": check_structure(measures, report, page_html)}
    checks_score = sum(part["points"] for part in checks.values())

    judge = None
    judge_file = out_dir / "judge.json"
    if not args.no_judge:
        if judge_file.exists() and not args.rejudge:
            judge = json.loads(judge_file.read_text(encoding="utf-8"))
        else:
            judge = run_judge(shots_dir, args.judge_model, args.judge_runs)
            judge_file.write_text(json.dumps(judge, indent=2, ensure_ascii=False), encoding="utf-8")
    quality = 0.35 * checks_score + 0.65 * judge["score"] if judge else checks_score
    page_economy = economy(measures)
    run_speed = speed(result) if result else None
    if run_speed and run_speed["score"] is not None:
        overall = 0.60 * quality + 0.25 * run_speed["score"] * min(1.0, quality / QUALITY_GATE) + 0.15 * page_economy["score"]
    else:
        overall = (0.60 * quality + 0.15 * page_economy["score"]) / 0.75

    data = {
        "page": page.as_posix(),
        "overall": round(overall, 1),
        "quality": round(quality, 1),
        "quality_basis": "checks + judge" if judge else "checks only (no judge)",
        "speed": run_speed["score"] if run_speed else None,
        "economy": page_economy["score"],
        "checks": {"score": round(checks_score, 1), **checks},
        "judge": judge,
        "speed_parts": run_speed,
        "economy_parts": page_economy,
        "run": {k: result.get(k) for k in ("label", "model", "mode", "wall_s", "num_turns", "total_cost_usd", "output_tokens_total",
                                          "thinking_tokens_total", "input_tokens_total", "est_minutes_at_15_tok_s")} if result else None,
        "page_measures": {k: measures.get(k) for k in ("visible_words", "bytes", "sections", "steps", "code_blocks", "tables", "chips", "toggles", "layout_problems")},
    }
    (out_dir / "score.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="run folder or an .html page")
    parser.add_argument("--out", type=Path, help="where measures/shots/score.json go (pages only; default runs/corpus/<stem>)")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge (quality = checks only)")
    parser.add_argument("--rejudge", action="store_true", help="ignore a cached judge.json")
    parser.add_argument("--judge-model", default="opus")
    parser.add_argument("--judge-runs", type=int, default=1, help="average this many judgements")
    parser.add_argument("--remeasure", action="store_true", help="re-run measure.py even if measures exist")
    args = parser.parse_args()

    if args.target.is_dir():
        page, out_dir = args.target / "out" / "index.html", args.target
        result_file = args.target / "result.json"
        result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else None
    else:
        page, out_dir, result = args.target, args.out or LOOP_DIR / "runs" / "corpus" / args.target.stem, None
    if not page.exists():
        sys.exit(f"no page at {page}")
    data = score(page, out_dir, result, args)
    summary = {k: data[k] for k in ("overall", "quality", "speed", "economy")}
    summary["checks"] = {k: data["checks"][k]["points"] for k in ("facts", "layout", "structure")}
    if data["judge"]:
        summary["judge"] = {"score": data["judge"]["score"], **data["judge"]["items"]}
        summary["verdict"] = data["judge"]["verdict"]
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
