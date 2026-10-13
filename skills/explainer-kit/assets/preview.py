"""Build a decision (options) or before/after chapter fragment from a small JSON file.

Usage: python preview.py decide.json --out frag-decide.html

The fragment uses the kit's `ev-pick` component (cards left, the selected card's panel right, switched by kit.js),
so it needs no CSS or script of its own. Text fields may contain inline HTML (<b>, <code>, <a href>).

{
  "name": "decide",                         section name, also the id prefix (lowercase letters/digits)
  "label": "Decision", "hint": "3 options",
  "title": "Which way to go",               chapter heading (data-part-title)
  "lede": "One sentence framing the question.",
  "options": [
    {"id": "a", "title": "A · Oxlint + oxfmt", "recommended": true,     ("selected": true picks the start card;
     "summary": "One line.",                                             default: recommended, else the first)
     "chips": [["ok", "263 rules migrate"], ["risk", "JS plugins alpha"]],  chip kinds: new removed risk decision ok accent neutral
     "rows": [{"kind": "ok", "label": "Keeps", "items": ["…", "…"]},     row kinds: ok new removed risk decision neutral;
              {"kind": "risk", "label": "Risks", "items": ["…"]}],       use the same labels in every option
     "effort": "~1–2 days: …",
     "code": {"file": "eslint-rules/local-plugin.mts", "add": "1-2",    optional: ≤ 8 real lines this option adds or
              "lines": ["import { x } from \"./x.mts\";", "export default x;"]}}   changes (add/del/hl: displayed line ranges)
  ],
  "flip": ["What would change the recommendation …"],                  optional, shown as a callout under the cards
  "details": [{"kind": "list", "title": "Sources", "html": "<ul>…</ul>"}]   optional ev-more toggle, one group each
}
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROW_KINDS = {"ok", "new", "removed", "risk", "decision", "neutral"}
CHIP_KINDS = {"new", "removed", "risk", "decision", "ok", "accent", "neutral"}
DETAIL_KINDS = {"code", "table", "list", "why", "chart", "trace", "risk", "file"}


def attr(value: str) -> str:
    return html.escape(value, quote=True)


def chips_html(chips: list) -> str:
    spans = []
    for kind, text in chips:
        if kind not in CHIP_KINDS:
            sys.exit(f"unknown chip kind {kind!r}; use one of {sorted(CHIP_KINDS)}")
        spans.append(f'<span class="ev-chip ev-chip--{kind}">{text}</span>')
    return f'<span class="ev-pick-chips">{"".join(spans)}</span>' if spans else ""


def card_html(name: str, option: dict, selected: bool) -> str:
    badge = ' <span class="ev-chip ev-chip--accent">Recommended</span>' if option.get("recommended") else ""
    summary = f'<span class="ev-pick-sum">{option["summary"]}</span>' if option.get("summary") else ""
    return (
        f'<button type="button" class="ev-pick-card" role="tab" id="{name}-{option["id"]}-card" '
        f'aria-controls="{name}-{option["id"]}" aria-selected="{str(selected).lower()}">'
        f'<span class="ev-pick-title">{option["title"]}{badge}</span>{summary}{chips_html(option.get("chips", []))}</button>'
    )


def panel_html(name: str, option: dict, selected: bool) -> str:
    rows = []
    for row in option.get("rows", []):
        kind = row.get("kind", "neutral")
        if kind not in ROW_KINDS:
            sys.exit(f"unknown row kind {kind!r}; use one of {sorted(ROW_KINDS)}")
        items = "".join(f"<li>{item}</li>" for item in row["items"])
        rows.append(f'<dt data-kind="{kind}">{row["label"]}</dt><dd><ul>{items}</ul></dd>')
    if option.get("effort"):
        rows.append(f'<dt data-kind="neutral">Effort</dt><dd>{option["effort"]}</dd>')
    code = code_html(option["code"]) if option.get("code") else ""
    hidden = "" if selected else " hidden"
    return (
        f'<div class="ev-pick-panel" role="tabpanel" id="{name}-{option["id"]}" aria-labelledby="{name}-{option["id"]}-card"{hidden}>'
        f'<h3>{option["title"]}</h3><dl class="ev-pick-rows">{"".join(rows)}</dl>{code}</div>'
    )


def code_html(code: dict) -> str:
    """A short real snippet as a wrapping kit code block (no sideways scroll in the narrow panel)."""
    lines = code["lines"] if isinstance(code.get("lines"), list) else str(code.get("text", "")).splitlines()
    marks = "".join(f' data-{key}="{attr(str(code[key]))}"' for key in ("add", "del", "hl") if code.get(key))
    file = f' data-file="{attr(code["file"])}"' if code.get("file") else ""
    return (f'<figure class="ev-code ev-code--wrap"{file}{marks}><pre><code>'
            f'{html.escape(chr(10).join(lines), quote=False)}</code></pre></figure>')


def flip_html(flip: list) -> str:
    if not flip:
        return ""
    items = "".join(f"<li>{item}</li>" for item in flip)
    return (
        '<div class="ev-callout ev-callout--decision"><span>What would change this</span>'
        f'<div><ul>{items}</ul></div></div>'
    )


def details_html(name: str, details: list) -> str:
    if not details:
        return ""
    for group in details:
        if group.get("kind", "list") not in DETAIL_KINDS:
            sys.exit(f"unknown details kind {group['kind']!r}; use one of {sorted(DETAIL_KINDS)}")
    what = "".join(f'<span data-kind="{g.get("kind", "list")}">{g["title"]}</span>' for g in details)
    groups = "".join(
        f'<div class="ev-group"><div class="ev-group-head" data-kind="{g.get("kind", "list")}"><h3>{g["title"]}</h3></div>{g["html"]}</div>'
        for g in details
    )
    return (
        f'<details class="ev-more" id="{name}-details" data-toc="{attr(details[0]["title"])}"><summary>'
        f'<span class="ev-more-what">{what}</span></summary><div class="ev-more-body">{groups}</div></details>'
    )


def build(data: dict) -> str:
    name = data["name"]
    if not re.fullmatch(r"[a-z0-9]+", name):
        sys.exit(f"name {name!r} must be lowercase letters/digits")
    options = data["options"]
    chosen = next((o for o in options if o.get("selected")), None) or next(
        (o for o in options if o.get("recommended")), options[0])
    cards = "".join(card_html(name, o, o is chosen) for o in options)
    panels = "".join(panel_html(name, o, o is chosen) for o in options)
    lede = f'<p class="ev-text">{data["lede"]}</p>' if data.get("lede") else ""
    return (
        f'<section class="ev-tab-content" data-tab="{name}" data-label="{attr(data.get("label", "Decision"))}" '
        f'data-hint="{attr(data.get("hint", f"{len(options)} options"))}" data-part-title="{attr(data["title"])}">\n'
        f'<div class="ev-secs"><section class="ev-sec" id="{name}-options" data-toc="Options">{lede}\n'
        f'<div class="ev-side ev-pick"><div><div class="ev-pick-cards" role="tablist" aria-label="Options" data-ev-anchor>{cards}</div>\n'
        f'{flip_html(data.get("flip", []))}</div>\n'
        f'<div class="ev-stick">{panels}</div></div>\n'
        f'{details_html(name, data.get("details", []))}\n'
        f'</section></div>\n</section>\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data", type=Path, help="chapter JSON")
    parser.add_argument("--out", type=Path, required=True, help="fragment to write, e.g. frag-decide.html")
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    args.out.write_text(build(data), encoding="utf-8")
    print(f"wrote {args.out} ({len(data['options'])} cards)")


if __name__ == "__main__":
    main()
