"""Screenshot an explainer page the same way for every run.

Usage: python shoot.py <page.html> <out-dir>

Writes desktop (1440 wide) and phone (390 wide) screenshots in dark and light, a full-page desktop screenshot
per mode, story screenshots (first, middle and last step on desktop, middle step on a phone), page.txt (the
page's text with every toggle and switchable panel opened, for a judge) and report.json with layout problems the eye can miss:
horizontal overflow, cut-off panels and code blocks, console errors, SVG text too small to read on a phone, and
scroll steps whose panel is out of view or covers the step.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = {"desktop": (1440, 900), "phone": (390, 844)}
MODES = ("dark", "light")
SMALLEST_READABLE_SVG_TEXT_PX = 9

CHECKS_JS = """
() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const label = el => el.tagName.toLowerCase()
    + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : '')
    + ' (' + Math.round(el.getBoundingClientRect().width) + 'px)';
  const over = [...document.querySelectorAll('body *')].filter(el => {
    const r = el.getBoundingClientRect();
    if (!(r.width > 0 && r.right > vw + 1)) return false;
    const scroller = el.closest('.ev-code-scroll, .ev-table-wrap, .ev-tablist');
    return !(scroller && scroller.getBoundingClientRect().right <= vw + 1);
  });
  const overflow = over.filter(el => !over.some(o => o !== el && o.contains(el))).slice(0, 10).map(label);
  const clippedCode = [...document.querySelectorAll('.ev-code')]
    .filter(el => {
      const s = el.querySelector('.ev-code-scroll') || el;
      return s.scrollWidth > s.clientWidth + 1;
    }).length;
  const sticks = [...document.querySelectorAll('.ev-stick')];
  const clippedSticky = sticks.filter(el => el.scrollHeight > el.clientHeight + 1).length;
  const pinnedShare = Math.max(0, ...sticks
    .filter(el => getComputedStyle(el).position === 'sticky')
    .map(el => el.getBoundingClientRect().height / vh));
  const steps = [...document.querySelectorAll('.ev-step')];
  let largestStepGap = 0;
  for (let i = 1; i < steps.length; i++) {
    const a = steps[i - 1].getBoundingClientRect(), b = steps[i].getBoundingClientRect();
    if (steps[i].parentElement === steps[i - 1].parentElement) largestStepGap = Math.max(largestStepGap, b.top - a.bottom);
  }
  const svgTexts = [...document.querySelectorAll('svg text')].filter(t => t.getBoundingClientRect().width > 0);
  const effectiveSize = t => {
    const ctm = t.getScreenCTM();
    return parseFloat(getComputedStyle(t).fontSize) * (ctm ? Math.hypot(ctm.a, ctm.b) : 1);
  };
  return {
    pageWidth: document.documentElement.scrollWidth, viewportWidth: vw,
    horizontalOverflow: document.documentElement.scrollWidth > vw + 1, overflowingElements: overflow,
    codeBlocks: document.querySelectorAll('.ev-code').length, codeBlocksScrollingSideways: clippedCode,
    stickyPanels: sticks.length, stickyPanelsCutOff: clippedSticky,
    pinnedPanelViewportShare: Math.round(pinnedShare * 100) / 100,
    stepCount: steps.length, largestStepGapPx: Math.round(largestStepGap),
    svgTexts: svgTexts.length,
    svgTextsTooSmall: svgTexts.filter(t => effectiveSize(t) < SMALLEST).length,
    sections: [...document.querySelectorAll('.ev-part-head')].map(h => h.id),
    pageHeight: document.documentElement.scrollHeight,
  };
}
""".replace("SMALLEST", str(SMALLEST_READABLE_SVG_TEXT_PX))

STEP_GROUPS_JS = """
() => [...document.querySelectorAll('.ev-side')]
  .map((side, index) => ({ index, steps: side.querySelectorAll('.ev-step').length,
                          section: (side.closest('[data-tab]') || { dataset: {} }).dataset.tab || '' }))
  .filter(group => group.steps > 0)
"""

SCROLL_TO_STEP_JS = """
([sideIndex, stepIndex]) => {
  const side = document.querySelectorAll('.ev-side')[sideIndex];
  const step = side.querySelectorAll('.ev-step')[stepIndex];
  const top = (window.EV && EV.stickyTop) ? EV.stickyTop() : 0;
  const line = top + (window.innerHeight - top) / 2;
  window.scrollTo({ top: window.scrollY + step.getBoundingClientRect().top - line + 20, behavior: 'instant' });
}
"""

STEP_STATE_JS = """
([sideIndex, stepIndex]) => {
  const side = document.querySelectorAll('.ev-side')[sideIndex];
  const step = side.querySelectorAll('.ev-step')[stepIndex].getBoundingClientRect();
  const stick = side.querySelector('.ev-stick');
  if (!stick) return { panelVisible: true, stepCovered: false };
  const panel = stick.getBoundingClientRect();
  const top = (window.EV && EV.stickyTop) ? EV.stickyTop() : 0;
  const visible = Math.max(0, Math.min(panel.bottom, innerHeight) - Math.max(panel.top, top));
  const overlap = Math.max(0, Math.min(panel.bottom, step.bottom) - Math.max(panel.top, step.top)) *
                  Math.max(0, Math.min(panel.right, step.right) - Math.max(panel.left, step.left));
  return {
    panelVisible: visible >= 0.6 * Math.min(panel.height, innerHeight - top),
    stepCovered: overlap > 0.3 * step.height * step.width,
  };
}
"""

PAGE_TEXT_JS = """
() => {
  document.querySelectorAll('details').forEach(d => d.open = true);
  document.querySelectorAll('[hidden]').forEach(el => el.hidden = false);
  const svgLabels = [...document.querySelectorAll('svg')]
    .map(svg => [...svg.querySelectorAll('text')].map(t => t.textContent.trim()).filter(Boolean).join(' | '))
    .filter(Boolean);
  const notRendered = [...document.querySelectorAll('.ev-tab-content *')]
    .filter(el => !['SCRIPT', 'STYLE', 'TEMPLATE'].includes(el.tagName) && getComputedStyle(el).display === 'none' &&
                  getComputedStyle(el.parentElement).display !== 'none')
    .map(el => el.textContent.replace(/\\s+/g, ' ').trim()).filter(Boolean);
  return document.body.innerText + '\\n\\n--- text inside SVG graphics ---\\n' + svgLabels.join('\\n') +
         '\\n\\n--- text in panels that are switched off until clicked ---\\n' + notRendered.join('\\n');
}
"""


def check_steps(tab, out: Path, key: str, viewport: str) -> list[dict]:
    """Scrolls every scroll step to the reading line and records whether its panel is in view and uncovered."""
    groups = tab.evaluate(STEP_GROUPS_JS)
    results = []
    for group_number, group in enumerate(groups):
        problems = {"panelOutOfView": 0, "stepCovered": 0}
        count = group["steps"]
        for step in range(count):
            tab.evaluate(SCROLL_TO_STEP_JS, [group["index"], step])
            tab.wait_for_timeout(250)
            state = tab.evaluate(STEP_STATE_JS, [group["index"], step])
            problems["panelOutOfView"] += not state["panelVisible"]
            problems["stepCovered"] += state["stepCovered"]
            is_story_shot = group_number == 0 and key.endswith("dark") and (
                step in (0, count // 2, count - 1) if viewport == "desktop" else step == count // 2)
            if is_story_shot:
                tab.screenshot(path=str(out / f"story-{viewport}-step{step + 1}.png"))
        results.append({"section": group["section"], "steps": count, **problems})
    tab.evaluate("() => window.scrollTo({ top: 0, behavior: 'instant' })")
    return results


def main(page_path: str, out_dir: str) -> None:
    page = Path(page_path).resolve()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for vp_name, (w, h) in VIEWPORTS.items():
            for mode in MODES:
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=mode)
                tab = ctx.new_page()
                errors = []
                tab.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                tab.on("console", lambda m, errors=errors: m.type == "error" and errors.append(m.text))
                tab.goto(page.as_uri(), wait_until="networkidle")
                tab.wait_for_timeout(500)
                key = f"{vp_name}-{mode}"
                tab.screenshot(path=str(out / f"{key}.png"))
                if vp_name == "desktop":
                    tab.screenshot(path=str(out / f"{key}-full.png"), full_page=True)
                report[key] = {**tab.evaluate(CHECKS_JS), "steps": check_steps(tab, out, key, vp_name)}
                if key == "desktop-dark":
                    (out / "page.txt").write_text(tab.evaluate(PAGE_TEXT_JS), encoding="utf-8")
                report[key]["errors"] = errors
                ctx.close()
        browser.close()
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["desktop-dark"], indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
