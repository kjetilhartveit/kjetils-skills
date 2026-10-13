# Fragment contract (explainer kit)

This file and the cheat sheet below are the kit's whole API: don't read `kit.css`, `kit.js` or `assemble.py`.
Chapters without their own script (story, decision, before/after) need only this file. A fragment with its own
script (clips, slides, video, code walkthrough) or a tabbed page also needs `SCRIPTS-AND-TABS.md`.

Every `explain-with-*` skill writes **one fragment file** per chapter (e.g. `story`, `code`, `fragile`, `deps`,
`complex`, `decide`, `clips`, `slides`, `video`). `assemble.py` merges the fragments into one page: the overview
on top, then the chapters, either as one scrollable page (`--page --toc`, the default for `explain-visually`) or
as tabs. A fragment can also be assembled alone with `--standalone`. `assemble.py` enforces the rules marked
**(checked)** and refuses to write the page if any of them fail.

In page mode each fragment is a chapter, and `NAME` is the name given with `--section NAME=FILE`.

## 1. Shape

```html
<section class="ev-tab-content" data-tab="story" data-label="Story" data-hint="6 steps" data-part-title="…">
  <style> [data-tab="story"] [data-step="3"] .story-x { … } </style>   <!-- optional -->
  … content built from kit components …
</section>
```

- Exactly one top-level `<section class="ev-tab-content" data-tab="NAME">`. No text or other elements outside it. **(checked)**
- `NAME` is lowercase letters/digits and equals the `--section NAME=` given to the assembler. **(checked)**
- `data-label` = tab text (defaults: Clips, Story, Code, Video, Slides). `data-hint` = 1–3 words shown
  next to it on wide screens (e.g. "6 animations", "3–4 files").
- No `id` on the section itself (the assembler sets `id="NAME"`, `role="tabpanel"`). **(checked)**
- No `<html> <head> <body> <title> <meta> <link> <iframe> <object> <embed>`. **(checked)**

## 2. Ids and names

- Every `id` starts with `NAME-` (`clips-backoff`, `code-chain`). The overview uses `ov-`. **(checked)**
- Ids are unique across the whole page. **(checked)** Bare tab names (`#clips`) are reserved for tab deep links.
- Your own classes are `NAME-…` (`clips-ring`). The `ev-` prefix is reserved for the kit. **(checked in CSS)**
- `@keyframes` names start with `NAME-`. **(checked)**

## 3. CSS

- At most one `<style>` inside the section. Every selector starts with `[data-tab="NAME"]`, also inside
  `@media` / `@supports`. **(checked)** No `@import`, `@font-face`, `@property`. **(checked)**
- Colours, fonts and radii come only from kit tokens (`var(--ev-…)`, list at the top of `kit.css`).
  Never a literal colour: the page has 4 themes × light/dark.
- Don't restyle kit components (`[data-tab="x"] .ev-chip {…}` gives a warning). If a component is missing,
  add it to the kit instead.

## 4. Content rules (from the user's feedback)

- Each section: **takeaway headline → one visual → at most 2–3 short sentences → optional `ev-more`.**
- Text is always fully readable; nothing meant to be read starts at `opacity: 0`.
- Details live behind `ev-more`, and **the summary names what is inside** (one item per group in the body),
  plus a short meta (e.g. "table · 7 rows"). Never a bare "Show details".
- Inside `ev-more`, give the reader visual help: one `ev-group` per summary item, highlighted code lines,
  diff gutter, numbered markers, chips for status, `is-hl` table rows, `ev-bars` for small numeric comparisons.
- Semantic colours are fixed and always paired with a glyph: new `+` green, removed `−` red, risk `!` red,
  decision `◆` amber, ok `✓` green. The accent is for "this is the point", not for status.
- Don't invent facts; `facts.md` is the source of truth.

## 5. Kit components (cheat sheet)

| need | markup |
|---|---|
| section list | `<div class="ev-secs">` of `<section class="ev-sec" id="NAME-x">` |
| section head | `<div class="ev-sec-head"><p class="ev-eyebrow"><span class="ev-n">2</span>Label</p><h2 class="ev-takeaway">One sentence.</h2></div>` |
| short text | `<p class="ev-text">` |
| static visual | `<figure class="ev-visual"><svg class="ev-svg" …>` with `ev-t-*`, `ev-node`, `ev-wire`, `ev-f-*` classes |
| SVG text | default 15px; `ev-t-sm` 14, `ev-t-xs` 12.5 (smallest), `ev-t-lg` 22 bold (values), `ev-t-num` 56 (ONE big counter only, never a label); colour `ev-t-muted\|faint\|acc\|risk\|new\|decide`; `ev-t-mono`, `ev-t-b`. Right-align values with `text-anchor="end"` |
| details | (summary reads as one line: rotating chevron, then the items joined by " · "; no "More" label) `<details class="ev-more"><summary><span class="ev-more-what"><span data-kind="table">Tick trace</span><span data-kind="why">Why 5 rows</span></span><span class="ev-more-meta">table · 7 rows</span></summary><div class="ev-more-body">…</div></details>` — kinds: `code table list why chart trace risk file` |
| group in details | `<div class="ev-group"><div class="ev-group-head" data-kind="table"><h3>Tick trace</h3><span class="ev-group-meta">…</span></div>…</div>` |
| code | `<figure class="ev-code" data-file="dir/file.ts" data-tag="proposed" data-start="1" data-add="4-7" data-del="" data-hl="9" data-focus data-marks="4:1, 9:2" data-groups="1-2:Existing guard; 4-7:New: back off"><pre><code>…HTML-escaped source…</code></pre><ol class="ev-code-notes"><li><span>note 1</span></li></ol></figure>` — line numbers are the displayed ones; `data-focus` dims unmarked lines; a group whose lines are all added turns green |
| table | `<div class="ev-table-wrap"><table class="ev-table">`; cells `ev-mono` / `ev-num`; rows `is-hl`, `is-muted`, `is-sep` |
| chip | `<span class="ev-chip ev-chip--new|removed|risk|decision|ok|accent|neutral">text</span>` |
| callout | `<div class="ev-callout ev-callout--decision|risk|new"><span>Decide</span><span>text</span></div>` |
| small bars | `<div class="ev-bars">` of `ev-k` / `<span class="ev-bar [is-cap]"><i style="--v:40%">` / `ev-v` |
| facts | `<dl class="ev-facts"><dt>…</dt><dd>…</dd></dl>` |
| jump list | `<ul class="ev-jump"><li><a href="#NAME-x"><span class="ev-n">1</span>Label</a></li></ul>` |
| text + sticky panel | `<div class="ev-side"><div>…steps / cards…</div><div class="ev-stick">…panel…</div></div>`: text left, panel right, panel centred on the first text box at rest and stuck in the vertical centre while scrolling. Stacks below 900px. Don't pad or space it yourself |
| story (scroll steps) | `<div class="ev-side ev-side--pin" data-ev-story>` with `<div class="ev-step">` boxes left and one SVG in the `ev-stick`. No script: the kit drives the steps, sets `data-step` on the panel and applies `data-on="2-4"` / `data-hl="3"` / `data-say="a\|b\|\|d"` on elements inside it. `ev-side--pin` spaces the steps and pins the panel on phones. See `explain-with-storytelling` |
| hero / numbers | `<div class="ev-bars ev-bars--hero">` of `<span class="ev-k">ESLint</span><span class="ev-bar [is-good\|is-muted\|is-cap]"><i style="--v:100%"></i></span><span class="ev-v"><b>44.0 s</b></span>`; `--v` is the value as % of the largest, so bars are to scale. HTML, so it stays legible on phones |
| options / before-after | generated: `python preview.py decide.json --out frag-decide.html` (see "Preview chapters from JSON") |
| wide tab | add `ev-wide` to the section to drop the 720px reading width |

## 6. The overview (coordinator only)

One `<header class="ev-overview">` with, in order: `p.ev-eyebrow` (context), `h1.ev-headline#ov-title`
(states the answer; wrap the key figure in `<em>`), `p.ev-lede` (ONE sentence), `figure.ev-hero` (ONE visual),
`p.ev-keyline` (2–4 short facts as `<span>`, plus at most one `<span class="ev-decide"><b>Decide</b> …</span>`).
Nothing else: no grid of info boxes. Its `<style>` selectors start with `.ev-overview`; ids start with `ov-`. **(checked)**

## 7. Page mode (one scrollable document)

```
python assemble.py --page --toc --title "Backoff explainer" --overview overview.html   --section story=frag-story.html --section code=frag-code.html --out index.html
```

- Same fragments as tabs; every section is visible at once and `EV.onShow` fires for all of them at load.
- Each section is opened by a part heading (`header.ev-part-head#NAME`): eyebrow = number · `data-label` · `data-hint`,
  `h2` = `data-part-title` (e.g. "How the code changes"), optional `p` = `data-part-lede`. Set these on the fragment's `<section>`.
- `--toc` adds a sticky chapter list on the left (≥1160px) that collapses to a sticky top bar with a dropdown below that.
  Entries: Overview (`#overview`), one per section, plus a sub-entry for every element in the fragment with
  `id` + `data-toc="Short label"` (story scene groups, code steps, details). Active entry follows the scroll.
- Side panels (story graphic, code panel, preview) go on the **right** with `ev-side` + `ev-stick`; the kit
  handles sticking, centring, the top bar offset (`EV.stickyTop()`, `var(--ev-sticky-top)`) and phone stacking.

## 8. Preview chapters from JSON

Decision (options) and before/after chapters are generated, with no HTML, CSS or script of their own:

```json
{"name": "decide", "label": "Decision", "hint": "3 options", "title": "Which way to go",
 "lede": "One sentence framing the question.",
 "options": [
   {"id": "a", "title": "A · Option name", "recommended": true, "summary": "One line.",
    "chips": [["ok", "263 rules migrate"], ["risk", "JS plugins alpha"]],
    "rows": [{"kind": "ok", "label": "Keeps", "items": ["…"]},
             {"kind": "removed", "label": "Loses", "items": ["…"]},
             {"kind": "decision", "label": "Fix first", "items": ["…"]},
             {"kind": "risk", "label": "Risks", "items": ["…"]}],
    "effort": "~1–2 days: what the work is",
    "code": {"file": "path/in/repo.json", "add": "2-3", "lines": ["{", "  \"real\": \"config\"", "}"]}}],
 "flip": ["What would change the recommendation"],
 "details": [{"kind": "list", "title": "Sources", "html": "<ul><li><a href=\"https://…\">…</a></li></ul>"}]}
```

Row kinds: `ok new removed risk decision neutral`; chip kinds as in the cheat sheet. `"selected": true` picks the
starting card (default: the recommended one). Text may contain inline `<b>`, `<code>`, `<a href>`. `code` (optional, per
option): ≤ 8 real lines, one string per line, shown under the rows with the file path; `add`/`del`/`hl` mark lines.
"What would change this" sits under the cards; `details` is one toggle below the chapter.

## 9. Checking

`python check.py index.html` opens the page on a desktop and a phone and lists only real problems (overflow,
cut-off panels or code, unreadable SVG labels, story panel out of view, console errors). Fix what it lists, run
it once more, stop.
