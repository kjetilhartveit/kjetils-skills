"""Deterministic page measures for an explainer page: size, structure and layout checks.

Usage:
    python measure.py <run-dir>              # expects <run-dir>/out/index.html; writes shots/ and measures.json there
    python measure.py <page.html> --out DIR  # any page, e.g. the baseline corpus

Size and structure come from the HTML (scripts and styles excluded from the word count); layout problems
(overflow, cut-off panels, console errors) come from shoot.py, which also writes the screenshots.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shoot import main as shoot  # noqa: E402

COUNTED_CLASSES = {
    "chapters": "ev-part-head",
    "steps": "ev-step",
    "code_blocks": "ev-code",
    "tables": "ev-table",
    "chips": "ev-chip",
    "toggles": "ev-more",
    "callouts": "ev-callout",
    "side_panels": "ev-stick",
    "visuals": "ev-visual",
    "clips": "ev-clip",
}


def class_tokens(page: str) -> Counter[str]:
    tokens: Counter[str] = Counter()
    for attribute in re.findall(r'class="([^"]*)"', page):
        tokens.update(attribute.split())
    return tokens


def fragment_styles(page: str) -> str:
    """The <style> blocks the agents wrote; the inlined kit.css (which defines the theme colours) is skipped."""
    return "".join(s for s in re.findall(r"<style\b.*?</style>", page, flags=re.S) if "kit.css" not in s)


def visible_text(page: str) -> str:
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    return html.unescape(body)


def page_measures(page_path: Path) -> dict:
    page = page_path.read_text(encoding="utf-8", errors="replace")
    words = visible_text(page).split()
    sections = re.findall(r'<section[^>]*\bdata-tab="([a-z0-9]+)"', page)
    tokens = class_tokens(page)
    return {
        "bytes": page_path.stat().st_size,
        "visible_words": len(words),
        "sections": sections,
        **{name: tokens[cls] for name, cls in COUNTED_CLASSES.items()},
        "external_links": len(set(re.findall(r'href="(https?://[^"]+)"', page))),
        "literal_colours_in_fragment_styles": len(re.findall(r"#[0-9a-fA-F]{3,8}\b", fragment_styles(page))),
    }


def layout_summary(report: dict) -> dict:
    problems = []
    for key, view in report.items():
        if view.get("horizontalOverflow"):
            problems.append(f"{key}: horizontal overflow ({view['pageWidth']}px on {view['viewportWidth']}px)")
        if view.get("stickyPanelsCutOff"):
            problems.append(f"{key}: {view['stickyPanelsCutOff']} sticky panel(s) cut off")
        if view.get("codeBlocksScrollingSideways"):
            problems.append(f"{key}: {view['codeBlocksScrollingSideways']} code block(s) scroll sideways")
        if key.startswith("phone") and view.get("pinnedPanelViewportShare", 0) > 0.6:
            problems.append(f"{key}: pinned panel takes {round(view['pinnedPanelViewportShare'] * 100)}% of the viewport")
        if key.startswith("phone") and view.get("svgTexts") and view["svgTextsTooSmall"] / view["svgTexts"] > 0.1:
            problems.append(f"{key}: {view['svgTextsTooSmall']}/{view['svgTexts']} SVG labels under 9px")
        for group in view.get("steps", []):
            bad = max(group["panelOutOfView"], group["stepCovered"])
            if bad:
                problems.append(f"{key}: {group['section']}: panel out of view or covering the step on {bad}/{group['steps']} steps")
        for error in view.get("errors", []):
            problems.append(f"{key}: console error: {error[:160]}")
    return {
        "layout_problems": problems,
        "page_height_desktop": report.get("desktop-dark", {}).get("pageHeight"),
        "page_height_phone": report.get("phone-dark", {}).get("pageHeight"),
        "largest_step_gap_desktop": report.get("desktop-dark", {}).get("largestStepGapPx"),
        "pinned_panel_share_phone": report.get("phone-dark", {}).get("pinnedPanelViewportShare"),
    }


def measure_page(page_path: Path, out_dir: Path) -> dict:
    shots_dir = out_dir / "shots"
    shoot(str(page_path), str(shots_dir))
    report = json.loads((shots_dir / "report.json").read_text(encoding="utf-8"))
    measures = {"page": page_path.as_posix(), **page_measures(page_path), **layout_summary(report)}
    (out_dir / "measures.json").write_text(json.dumps(measures, indent=2), encoding="utf-8")
    return measures


def measure_run(run_dir: Path) -> dict:
    return measure_page(run_dir / "out" / "index.html", run_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="run folder or an .html page")
    parser.add_argument("--out", type=Path, help="where to write shots/ and measures.json (pages only)")
    args = parser.parse_args()
    if args.target.is_dir():
        measures = measure_run(args.target)
    else:
        measures = measure_page(args.target, args.out or args.target.parent / (args.target.stem + "-measures"))
    print(json.dumps({k: v for k, v in measures.items() if k != "page"}, indent=2))


if __name__ == "__main__":
    main()
