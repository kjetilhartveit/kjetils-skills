"""Screenshot an explainer page the same way for every run.

Usage: python shoot.py <page.html> <out-dir>

Writes desktop (1440 wide) and phone (390 wide) screenshots in dark and light, a full-page
desktop screenshot per mode, and report.json with layout problems the eye can miss:
horizontal overflow, code blocks cut off (scrollable) and console errors.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = {"desktop": (1440, 900), "phone": (390, 844)}
MODES = ("dark", "light")

CHECKS_JS = """
() => {
  const vw = document.documentElement.clientWidth;
  const overflow = [...document.querySelectorAll('body *')]
    .filter(el => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.right > vw + 1 && !el.closest('.ev-code-scroll, .ev-table-wrap, .ev-tablist, .ev-stick');
    })
    .slice(0, 10)
    .map(el => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').join('.') : ''));
  const clippedCode = [...document.querySelectorAll('.ev-code')]
    .filter(el => {
      const s = el.querySelector('.ev-code-scroll') || el;
      return s.scrollWidth > s.clientWidth + 1;
    }).length;
  const clippedSticky = [...document.querySelectorAll('.ev-stick')]
    .filter(el => el.scrollHeight > el.clientHeight + 1).length;
  return {
    pageWidth: document.documentElement.scrollWidth, viewportWidth: vw,
    horizontalOverflow: document.documentElement.scrollWidth > vw + 1, overflowingElements: overflow,
    codeBlocks: document.querySelectorAll('.ev-code').length, codeBlocksScrollingSideways: clippedCode,
    stickyPanels: document.querySelectorAll('.ev-stick').length, stickyPanelsCutOff: clippedSticky,
    sections: [...document.querySelectorAll('.ev-part-head')].map(h => h.id),
    pageHeight: document.documentElement.scrollHeight,
  };
}
"""


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
                report[key] = {**tab.evaluate(CHECKS_JS), "errors": errors}
                ctx.close()
        browser.close()
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["desktop-dark"], indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
