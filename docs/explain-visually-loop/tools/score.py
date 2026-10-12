"""Score one explainer run (or a bare page) as one comparable number plus a breakdown.

Usage:
    python score.py <run-dir>                 # expects out/index.html; uses result.json for cost/speed
    python score.py <page.html> --out DIR     # a bare page (e.g. the corpus); no cost/speed part
    options: --no-judge (deterministic parts only), --judge-model opus, --remeasure

Writes score.json next to measures.json. The rubric and weights are documented in ../scoring.md:

    quality  Q = 0.35 * checks + 0.65 * judge                         (0-100; checks are deterministic)
    economy  S = mean(words band, bytes, chapters)                    (0-100)
    speed    E = weighted output tokens, wall time, turns, cost, context (0-100; runs only)
    overall    = 0.60 Q + 0.25 E * min(1, Q / 80) + 0.15 S            (runs)
               = (0.60 Q + 0.15 S) / 0.75                             (bare pages)

The judge is blind: it gets a temporary folder with the facts file, the page text and screenshots under neutral
names, never the run's label, path or transcript.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
LOOP_DIR = TOOLS_DIR.parent
FACTS_FILE = LOOP_DIR / "inputs" / "facts-oxlint.md"
sys.path.insert(0, str(TOOLS_DIR))

# Facts the page needs to answer the question; each is a regex over the page text (any one alternative counts).
KEY_FACTS = {
    "names the Oxc formatter oxfmt": r"\boxfmt\b",
    "oxlint migrator keeps 263 rules": r"\b263\b",
    "Biome keeps 163 (or 152) of 295 rules / about half": r"\b(163|152)\b[^.]{0,40}\b295\b|\b55\s?%|\b45\s?%|about half|roughly half|almost half",
    "lint time compared in seconds": r"\b(44(\.0)?|47(\.3)?|29\.4|39\.4)\s?s\b[\s\S]{0,400}?\b\d(\.\d)?\s?s\b",
    "react-x typed rule crashes / must be dropped": r"(crash|190 files|185 files|leaked-conditional)",
    "Biome ignores eslint-disable comments": r"biome-ignore|ignores? (the |all |every )?(~?\d+ )?eslint-disable",
    "low-risk path: oxfmt first, keep ESLint": r"oxfmt (only|first)|formatter first|keep(ing)? eslint|eslint stays|format(ter)? half first",
    "formatting is not enforced today / drift": r"not enforced|drift|nothing checks|no format(ting)? check|14[69] files",
    "JS plugins are alpha (risk)": r"\balpha\b",
    "effort sized per option": r"\b\d(\s?[–-]\s?\d)?\s?(days?|hours?)\b|half a day|half-day",
    "lost no-restricted-syntax path checks": r"no-restricted-syntax|path checks?|vi\.mock",
    "what would change the recommendation": r"would change|would flip|what changes the|revisit (if|when)|switch (to biome )?(if|when)|reconsider",
}
SOURCE_LINK = r'href="https?://(www\.)?(oxc\.rs|biomejs\.dev|github\.com/(oxc-project|biomejs))'
# Universal claims the facts contradict (one rule crashes, path checks are lost, Biome drops 132 rules).
OVERCLAIMS = {
    "every/all rules carry over": r"(?<!nearly )(?<!almost )\b(every|all)( of the| \d+)? (eslint |lint )?rules? (carr(y|ies)|are kept|is kept|survive|migrate)",
    "every plugin family carries over": r"\b(every|all)( \d+)? plugin famil(y|ies)[^.]{0,40}carr",
    "drop-in / no rules lost": r"drop-in replacement|no rules? (are |is )?lost|without losing (a|any) rules?|zero (rule|config) changes",
}
JUDGE_CRITERIA = {
    "headline": (15, "The overview headline and lede answer the question (which tool, and the trade-off) with the key numbers, before any scrolling."),
    "accuracy": (20, "Substance: what the page says works, breaks, is kept, lost or recommended agrees with facts.md. Overclaims and universals ('every rule carries over', 'runs our rules as they are'), contradictions and invented findings are major faults. Judge numbers under 'numbers', not here."),
    "numbers": (5, "Numbers match facts.md (timings, rule and file counts, versions), are internally consistent and nothing is invented (e.g. an unmeasured warm-cache time)."),
    "story": (15, "The story chapter has an arc (today -> problem -> change -> result/risks) and ONE graphic that evolves step by step (check the story screenshots), concrete and to scale, rather than a static dashboard or a sequence of unrelated pictures."),
    "decision": (20, "Decision support: 2-3 options including a cautious one, a clear recommendation, effort per option, risks with concrete fixes, and what would change the recommendation."),
    "concision": (15, "Concise but complete: a reader gets the answer quickly and can find the details; no padding, no repetition of the same numbers in every block, no chapters that restate each other. Penalise thin pages that leave out facts a decision needs just as much as bloated ones."),
    "visual": (10, "Visual quality in the screenshots: clean, legible on desktop and phone (390 px), both themes finished, nothing cut off, overlapping or empty."),
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
    },
    "required": [*JUDGE_CRITERIA, "factual_errors"],
}
JUDGE_PROMPT = """You are grading an explainer web page that answers this user request in a code repository:

  "We're looking to move away from eslint and prettier to oxlint and oxprettier or Biome. Can you help me explore this? Explain visually"

Files in the current folder (read them all with the Read tool before grading):
- facts.md: the ground truth. Everything the page claims should be supported by it.
- page.txt: the page's full text, with every toggle opened; SVG labels are listed at the end.
- shots/*.png: desktop-dark.png and desktop-light.png (first screen), phone-dark.png and phone-light.png (first screen
  at 390 px), desktop-dark-full.png (whole page, scaled down), story-desktop-step*.png (the story chapter at its first,
  middle and last step), story-phone-step*.png (the story's middle step on a phone). Some may be missing if the page has no story.

A great page, for reference: states the answer and trade-off in the headline; one to-scale hero; a short story with
one evolving graphic; a decision chapter with a recommended option, a cautious option, effort, risks with fixes and
what would change the decision; about 1,000-1,800 words; each key number has one home; legible on a phone.

Score each criterion 0-10 (10 = as good as it reasonably gets, 5 = mediocre, 0 = missing or wrong):
{criteria}

Also list every factual error or overclaim you find (quote the page, cite the fact it contradicts). Be strict and
consistent; do not reward length for its own sake."""

TOKENS_ZERO_SCORE = 60_000
SPEED_SCALES = {  # (weight, value scoring 100, value scoring 0)
    "output_tokens_total": (0.50, 10_000, TOKENS_ZERO_SCORE),
    "wall_s": (0.15, 120, 1200),
    "num_turns": (0.10, 10, 80),
    "total_cost_usd": (0.15, 0.3, 3.0),
    "input_tokens_total": (0.10, 300_000, 3_000_000),
}


def linear(value: float, best: float, worst: float) -> float:
    """100 at `best`, 0 at `worst`, linear in between and clamped."""
    return max(0.0, min(100.0, 100 * (worst - value) / (worst - best)))


def page_text(shots_dir: Path, page_html: str) -> str:
    text_file = shots_dir / "page.txt"
    if text_file.exists():
        return text_file.read_text(encoding="utf-8")
    from measure import visible_text

    return visible_text(page_html)


def check_facts(text: str, page_html: str) -> dict:
    flat = re.sub(r"\s+", " ", text)
    found = {name: bool(re.search(pattern, flat, re.I)) for name, pattern in KEY_FACTS.items()}
    found["links to oxc.rs / biomejs.dev sources"] = bool(re.search(SOURCE_LINK, page_html, re.I))
    overclaims = [
        f"{name}: ...{flat[max(0, m.start() - 50):m.end() + 30]}..."
        for name, pattern in OVERCLAIMS.items()
        for m in re.finditer(pattern, flat, re.I)
    ]
    points = 40 * sum(found.values()) / len(found) - min(20, 10 * len(overclaims))
    return {"points": round(max(0.0, points), 1), "max": 40, "found": found, "overclaims": overclaims}


def check_layout(report: dict) -> dict:
    penalties = []

    def penalise(points: float, why: str) -> None:
        penalties.append((points, why))

    for key, view in report.items():
        phone = key.startswith("phone")
        if view.get("horizontalOverflow"):
            penalise(5 if phone else 3, f"{key}: page {view['pageWidth']}px wide on {view['viewportWidth']}px")
        if view.get("stickyPanelsCutOff"):
            penalise(2.5, f"{key}: {view['stickyPanelsCutOff']} sticky panel(s) cut off")
        if view.get("codeBlocksScrollingSideways"):
            penalise(min(2.5, 0.5 * view["codeBlocksScrollingSideways"]), f"{key}: {view['codeBlocksScrollingSideways']} code block(s) scroll sideways")
        if view.get("errors"):
            penalise(2.5, f"{key}: {len(view['errors'])} console error(s)")
        if phone and view.get("svgTexts"):
            share = view["svgTextsTooSmall"] / view["svgTexts"]
            if share > 0.1:
                penalise(round(4 * share, 1), f"{key}: {view['svgTextsTooSmall']}/{view['svgTexts']} SVG labels under 9px")
        for group in view.get("steps", []):
            bad = max(group["panelOutOfView"], group["stepCovered"])
            if bad:
                penalise(round(4 * bad / group["steps"], 1), f"{key}: {group['section']}: panel out of view or covering the step on {bad}/{group['steps']} steps")
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
    words_score = 100.0 if 1000 <= words <= 1800 else linear(words, 1800, 5000) if words > 1800 else linear(words, 1000, 400)
    chapters = len(measures["sections"])
    parts = {
        "words": round(words_score, 1),
        "bytes": round(linear(measures["bytes"], 130_000, 300_000), 1),
        "chapters": {0: 0, 1: 40, 2: 80, 3: 100, 4: 100, 5: 70, 6: 40}.get(chapters, 10),
    }
    return {"score": round(sum(parts.values()) / len(parts), 1), "parts": parts}


def speed(result: dict) -> dict:
    parts = {
        key: round(linear(float(result.get(key) or 0), best, worst), 1)
        for key, (_, best, worst) in SPEED_SCALES.items()
    }
    score = sum(SPEED_SCALES[key][0] * value for key, value in parts.items())
    return {"score": round(score, 1), "parts": parts, "raw": {key: result.get(key) for key in SPEED_SCALES}}


def run_judge(shots_dir: Path, model: str) -> dict:
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
            "--no-session-persistence", "--json-schema", json.dumps(JUDGE_SCHEMA),
        ]
        completed = subprocess.run(
            command, cwd=blind_dir, input=JUDGE_PROMPT.format(criteria=criteria), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=900,
        )
    try:
        verdict = json.loads(completed.stdout)["structured_output"]
        cost = json.loads(completed.stdout).get("total_cost_usd")
    except (json.JSONDecodeError, KeyError, TypeError):
        sys.exit(f"judge failed:\n{completed.stdout[-2000:]}\n{completed.stderr[-2000:]}")
    weighted = sum(weight * verdict[name]["score"] / 10 for name, (weight, _) in JUDGE_CRITERIA.items())
    return {"score": round(weighted, 1), "model": model, "cost_usd": cost, "verdict": verdict}


def score(page: Path, out_dir: Path, result: dict | None, use_judge: bool, judge_model: str, remeasure: bool) -> dict:
    measures_file = out_dir / "measures.json"
    shots_dir = out_dir / "shots"
    if remeasure or not measures_file.exists() or not (shots_dir / "page.txt").exists():
        from measure import measure_page

        measure_page(page, out_dir)
    measures = json.loads(measures_file.read_text(encoding="utf-8"))
    report = json.loads((shots_dir / "report.json").read_text(encoding="utf-8"))
    page_html = page.read_text(encoding="utf-8", errors="replace")
    text = page_text(shots_dir, page_html)

    checks = {"facts": check_facts(text, page_html), "layout": check_layout(report), "structure": check_structure(measures, report, page_html)}
    checks_score = sum(part["points"] for part in checks.values())
    judge = run_judge(shots_dir, judge_model) if use_judge else None
    quality = 0.35 * checks_score + 0.65 * judge["score"] if judge else checks_score
    page_economy = economy(measures)
    run_speed = speed(result) if result else None

    if run_speed:
        overall = 0.60 * quality + 0.25 * run_speed["score"] * min(1.0, quality / 80) + 0.15 * page_economy["score"]
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
        "economy_parts": page_economy,
        "speed_parts": run_speed,
        "page_measures": {k: measures[k] for k in ("visible_words", "bytes", "sections", "steps", "code_blocks", "tables", "chips", "toggles")},
    }
    (out_dir / "score.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="run folder or an .html page")
    parser.add_argument("--out", type=Path, help="where measures/shots/score.json go (pages only)")
    parser.add_argument("--no-judge", action="store_true", help="skip the LLM judge (quality = checks only)")
    parser.add_argument("--judge-model", default="opus")
    parser.add_argument("--remeasure", action="store_true", help="re-run measure.py even if measures exist")
    args = parser.parse_args()

    if args.target.is_dir():
        page, out_dir = args.target / "out" / "index.html", args.target
        result_file = args.target / "result.json"
        result = json.loads(result_file.read_text(encoding="utf-8")) if result_file.exists() else None
    else:
        page, out_dir, result = args.target, args.out or args.target.parent / (args.target.stem + "-measures"), None
    if not page.exists():
        sys.exit(f"no page at {page}")
    data = score(page, out_dir, result, not args.no_judge, args.judge_model, args.remeasure)
    summary = {k: data[k] for k in ("overall", "quality", "speed", "economy")}
    summary["checks"] = {k: data["checks"][k]["points"] for k in ("facts", "layout", "structure")}
    if data["judge"]:
        summary["judge"] = {k: v["score"] for k, v in data["judge"]["verdict"].items() if isinstance(v, dict)}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
