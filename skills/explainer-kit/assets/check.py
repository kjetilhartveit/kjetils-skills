"""Check an assembled explainer page on a desktop and a phone, and list only what needs fixing.

Usage: python check.py index.html [--shots DIR]

Opens the page at 1440x900 and 390x844 (dark), scrolls every scroll step to the reading line and prints one line
per problem: page wider than the screen, sticky panels or code blocks cut off, SVG labels too small to read on a
phone, story panels out of view or covering their step, and console errors. Exit code 0 = nothing to fix.
--shots saves a desktop and a phone screenshot of the first screen, if you want to look once.

Needs Python Playwright (`pip install playwright && playwright install chromium`). If it is missing, skip the
check rather than writing your own.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

VIEWPORTS = {"desktop": (1440, 900), "phone": (390, 844)}
SMALLEST_READABLE_SVG_TEXT_PX = 9

PAGE_JS = """
(smallest) => {
  const vw = document.documentElement.clientWidth;
  const where = el => { const s = el.closest('[id]'); return s ? '#' + s.id : el.tagName.toLowerCase(); };
  const wide = [...document.querySelectorAll('body *')].filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.right > vw + 1 && !el.closest('.ev-code-scroll, .ev-table-wrap, .ev-tablist, .ev-stick');
  });
  const size = t => { const m = t.getScreenCTM(); return parseFloat(getComputedStyle(t).fontSize) * (m ? Math.hypot(m.a, m.b) : 1); };
  const texts = [...document.querySelectorAll('svg text')].filter(t => t.getBoundingClientRect().width > 0);
  const small = texts.filter(t => size(t) < smallest);
  return {
    pageWidth: document.documentElement.scrollWidth, viewportWidth: vw,
    wideElements: [...new Set(wide.slice(0, 5).map(where))],
    cutPanels: [...document.querySelectorAll('.ev-stick')].filter(el => el.scrollHeight > el.clientHeight + 1).map(where),
    sidewaysCode: [...document.querySelectorAll('.ev-code')].filter(el => {
      const s = el.querySelector('.ev-code-scroll') || el; return s.scrollWidth > s.clientWidth + 1; }).map(where),
    smallSvgText: [...new Set(small.map(t => where(t.closest('svg'))))], smallCount: small.length, textCount: texts.length,
  };
}
"""

STEP_JS = """
([sideIndex, stepIndex]) => {
  const side = document.querySelectorAll('.ev-side')[sideIndex];
  const steps = side.querySelectorAll('.ev-step');
  if (stepIndex >= steps.length) return null;
  const top = window.EV ? EV.stickyTop() : 0, line = top + (innerHeight - top) / 2;
  window.scrollTo({ top: scrollY + steps[stepIndex].getBoundingClientRect().top - line + 20, behavior: 'instant' });
  return true;
}
"""

STEP_STATE_JS = """
([sideIndex, stepIndex]) => {
  const side = document.querySelectorAll('.ev-side')[sideIndex];
  const step = side.querySelectorAll('.ev-step')[stepIndex].getBoundingClientRect();
  const stick = side.querySelector(':scope > .ev-stick');
  if (!stick) return { panelVisible: true, stepCovered: false, where: '' };
  const panel = stick.getBoundingClientRect(), top = window.EV ? EV.stickyTop() : 0;
  const visible = Math.max(0, Math.min(panel.bottom, innerHeight) - Math.max(panel.top, top));
  const overlap = Math.max(0, Math.min(panel.bottom, step.bottom) - Math.max(panel.top, step.top)) *
                  Math.max(0, Math.min(panel.right, step.right) - Math.max(panel.left, step.left));
  const owner = side.closest('[id]');
  return { panelVisible: visible >= 0.6 * Math.min(panel.height, innerHeight - top),
           stepCovered: overlap > 0.3 * step.height * step.width, where: owner ? '#' + owner.id : '' };
}
"""


def step_problems(tab, viewport: str) -> list[str]:
    problems = []
    side_count = tab.evaluate("() => document.querySelectorAll('.ev-side').length")
    for side in range(side_count):
        out_of_view, covered, where = [], [], ""
        step = 0
        while tab.evaluate(STEP_JS, [side, step]):
            tab.wait_for_timeout(150)
            state = tab.evaluate(STEP_STATE_JS, [side, step])
            where = state["where"]
            if not state["panelVisible"]:
                out_of_view.append(step + 1)
            if state["stepCovered"]:
                covered.append(step + 1)
            step += 1
        if out_of_view:
            fix = " (add ev-side--pin to pin the panel on phones)" if viewport == "phone" else " (shorten the panel)"
            problems.append(f"{viewport}: {where} panel out of view on steps {out_of_view}{fix}")
        if covered:
            problems.append(f"{viewport}: {where} panel covers steps {covered} (make the panel shorter)")
    return problems


def check(page: Path, shots: Path | None) -> list[str]:
    from playwright.sync_api import sync_playwright

    problems = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for viewport, (width, height) in VIEWPORTS.items():
            context = browser.new_context(viewport={"width": width, "height": height}, color_scheme="dark")
            tab = context.new_page()
            errors: list[str] = []
            tab.on("pageerror", lambda e: errors.append(str(e)))
            tab.on("console", lambda m: m.type == "error" and errors.append(m.text))
            tab.goto(page.resolve().as_uri(), wait_until="networkidle")
            tab.wait_for_timeout(400)
            if shots:
                shots.mkdir(parents=True, exist_ok=True)
                tab.screenshot(path=str(shots / f"{viewport}.png"))
            found = tab.evaluate(PAGE_JS, SMALLEST_READABLE_SVG_TEXT_PX)
            if found["pageWidth"] > found["viewportWidth"] + 1:
                problems.append(f"{viewport}: page is {found['pageWidth']}px wide on a {found['viewportWidth']}px screen; too wide: {', '.join(found['wideElements'])}")
            for where in found["cutPanels"]:
                problems.append(f"{viewport}: sticky panel in {where} is taller than the screen and gets cut off")
            for where in found["sidewaysCode"]:
                problems.append(f"{viewport}: code block in {where} scrolls sideways (shorten or wrap the long lines)")
            if viewport == "phone" and found["smallCount"] > 0.1 * max(1, found["textCount"]):
                problems.append(f"phone: {found['smallCount']} SVG labels render under {SMALLEST_READABLE_SVG_TEXT_PX}px in {', '.join(found['smallSvgText'])} (narrower viewBox, bigger or fewer labels, or HTML ev-bars)")
            problems += step_problems(tab, viewport)
            problems += [f"{viewport}: console error: {error[:200]}" for error in errors]
            context.close()
        browser.close()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("page", type=Path)
    parser.add_argument("--shots", type=Path, help="save desktop.png and phone.png of the first screen here")
    args = parser.parse_args()
    try:
        problems = check(args.page, args.shots)
    except ImportError:
        print("Playwright is not installed: skip this check (don't write your own).")
        return 0
    if not problems:
        print("OK: nothing to fix. Stop checking.")
        return 0
    print("Fix only these, run check.py once more, then stop (don't chase anything else):")
    print("\n".join(f"- {problem}" for problem in dict.fromkeys(problems)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
