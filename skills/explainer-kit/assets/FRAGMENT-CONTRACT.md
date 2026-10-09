# Fragment contract (explainer kit)

Every `explain-with-*` skill writes **one fragment file** per chapter (e.g. `story`, `code`, `fragile`, `deps`,
`complex`, `decide`, `clips`, `slides`, `video`). `assemble.py` merges the fragments into one page: the overview
on top, then the chapters, either as one scrollable page (`--page --toc`, the default for `explain-visually`) or
as tabs. A fragment can also be assembled alone with `--standalone`. `assemble.py` enforces the rules marked
**(checked)** and refuses to write the page if any of them fail.

The examples below say "tab" for historical reasons: in page mode each fragment is a chapter, and `NAME` is the
name given with `--section NAME=FILE`.

## 1. Shape

```html
<section class="ev-tab-content" data-tab="clips" data-label="Clips" data-hint="short animations">
  <style> [data-tab="clips"] .clips-ring { … } </style>
  … content built from kit components …
  <script>
  (function () {
    "use strict";
    EV.onShow("clips", function (panel, info) {
      if (!info.first) return;            // build once
      EV.clip(panel.querySelector("#clips-backoff-clip"), { duration: 12, setup: …, draw: … });
    });
  })();
  </script>
</section>
```

- Exactly one top-level `<section class="ev-tab-content" data-tab="NAME">`. No text or other elements outside it. **(checked)**
- `NAME` is lowercase letters/digits and equals the `--tab NAME=` given to the assembler. **(checked)**
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

- One `<style>` inside the section. Every selector starts with `[data-tab="NAME"]`, also inside
  `@media` / `@supports`. **(checked)** No `@import`, `@font-face`, `@property`. **(checked)**
- Colours, fonts and radii come only from kit tokens (`var(--ev-…)`, list at the top of `kit.css`).
  Never a literal colour: the page has 4 themes × light/dark.
- Don't restyle kit components (`[data-tab="x"] .ev-chip {…}` gives a warning). If a component is missing,
  add it to the kit instead.

## 4. Script

- Inline scripts are wrapped in an IIFE `(function () { … })();`. **(checked)** No globals; query inside your
  own section (`panel.querySelector`), not `document.querySelector` (warning).
- `EV` exists before your script runs (kit.js is in `<head>`). Build things in **`EV.onShow(NAME, fn)`**:
  `fn(panel, {first})` runs whenever the tab becomes visible (and immediately in standalone pages).
  Hidden tabs are `display:none`, so measuring (`getBBox`, `getTotalLength`, scroll positions,
  IntersectionObserver setup) must happen there. Use `info.first` to build once; re-measure on every show.
- `EV.onHide(NAME, fn)` or `panel.addEventListener("ev:tabhide", …)` to pause your own animations.
  Players made with `EV.clip` pause on hide by themselves.
- Raw events, if you prefer: `ev:tabshow` / `ev:tabhide` CustomEvents on the section, `detail: {tab, first}`.
- External scripts only from `https://cdnjs.cloudflare.com/`, `https://cdn.jsdelivr.net/npm/`,
  `https://unpkg.com/`, pinned to an exact `x.y.z`. **(checked)** The same `src` in two fragments is loaded once.
- Respect `prefers-reduced-motion` (EV.clip does: no autoplay, end frame shown).

## 5. Content rules (from the user's feedback)

- Each section: **takeaway headline → one visual → at most 2–3 short sentences → optional `ev-more`.**
- Text is always fully readable; nothing meant to be read starts at `opacity: 0`.
- Details live behind `ev-more`, and **the summary names what is inside** (one item per group in the body),
  plus a short meta (e.g. "table · 7 rows"). Never a bare "Show details".
- Inside `ev-more`, give the reader visual help: one `ev-group` per summary item, highlighted code lines,
  diff gutter, numbered markers, chips for status, `is-hl` table rows, `ev-bars` for small numeric comparisons.
- Semantic colours are fixed and always paired with a glyph: new `+` green, removed `−` red, risk `!` red,
  decision `◆` amber, ok `✓` green. The accent is for "this is the point", not for status.
- Don't invent facts; the content brief is the source of truth.

## 6. Kit components (cheat sheet)

| need | markup |
|---|---|
| section list | `<div class="ev-secs">` of `<section class="ev-sec" id="NAME-x">` |
| section head | `<div class="ev-sec-head"><p class="ev-eyebrow"><span class="ev-n">2</span>Label</p><h2 class="ev-takeaway">One sentence.</h2></div>` |
| short text | `<p class="ev-text">` |
| static visual | `<figure class="ev-visual"><svg class="ev-svg" …>` with `ev-t-*`, `ev-node`, `ev-wire`, `ev-f-*` classes |
| animated clip | `<figure class="ev-clip" id="NAME-x" aria-label="…">` + `EV.clip(el, {duration, width, height, setup(svg), draw(t, svg), caption})`; helpers in `EV.svg` (`el`, `text`, `win`, `easeIO`, `easeOut`, `setClass`, `setText`) |
| details | (summary reads as one line: rotating chevron, then the items joined by " · "; no "More" label) `<details class="ev-more"><summary><span class="ev-more-what"><span data-kind="table">Tick trace</span><span data-kind="why">Why 5 rows</span></span><span class="ev-more-meta">table · 7 rows</span></summary><div class="ev-more-body">…</div></details>` — kinds: `code table list why chart trace risk file` |
| group in details | `<div class="ev-group"><div class="ev-group-head" data-kind="table"><h3>Tick trace</h3><span class="ev-group-meta">…</span></div>…</div>` |
| code | `<figure class="ev-code" data-file="dir/file.ts" data-tag="proposed" data-start="1" data-add="4-7" data-del="" data-hl="9" data-focus data-marks="4:1, 9:2" data-groups="1-2:Existing guard; 4-7:New: back off"><pre><code>…HTML-escaped source…</code></pre><ol class="ev-code-notes"><li><span>note 1</span></li></ol></figure>` — line numbers are the displayed ones; `data-focus` dims unmarked lines; a group whose lines are all added turns green |
| table | `<div class="ev-table-wrap"><table class="ev-table">`; cells `ev-mono` / `ev-num`; rows `is-hl`, `is-muted`, `is-sep` |
| chip | `<span class="ev-chip ev-chip--new|removed|risk|decision|ok|accent|neutral">text</span>` |
| callout | `<div class="ev-callout ev-callout--decision|risk|new"><span>Decide</span><span>text</span></div>` |
| small bars | `<div class="ev-bars">` of `ev-k` / `<span class="ev-bar [is-cap]"><i style="--v:40%">` / `ev-v` |
| facts | `<dl class="ev-facts"><dt>…</dt><dd>…</dd></dl>` |
| jump list | `<ul class="ev-jump"><li><a href="#NAME-x"><span class="ev-n">1</span>Label</a></li></ul>` |
| text + sticky panel | `<div class="ev-side"><div>…steps / cards…</div><div class="ev-stick"><div>…panel…</div></div></div>` — text left, panel right and vertically centred below the top bar; stacks below 900px (override the stacking per skill, e.g. pin the graphic at the top on phones) |
| wide tab | add `ev-wide` to the section to drop the 720px reading width |

## 7. The overview (coordinator only)

One `<header class="ev-overview">` with, in order: `p.ev-eyebrow` (context), `h1.ev-headline#ov-title`
(states the answer; wrap the key figure in `<em>`), `p.ev-lede` (ONE sentence), `figure.ev-hero` (ONE visual),
`p.ev-keyline` (2–4 short facts as `<span>`, plus at most one `<span class="ev-decide"><b>Decide</b> …</span>`).
Nothing else: no grid of info boxes. Its `<style>` selectors start with `.ev-overview`; ids start with `ov-`. **(checked)**

## 8. Assembling

```
python assemble.py --title "Refresh tick backoff" --overview overview.html \
  --tab clips=frag-clips.html --tab story=frag-story.html --tab code=frag-code.html --out index.html
python assemble.py --title "Backoff in 90 seconds" --standalone frag-video.html [--overview ov.html] --out index.html
```

Options: `--default TAB` (default `clips`), `--theme violet|ocean|amber|aurora` (first-load theme; the viewer's
own pick is remembered). Deep links: `#clips`, `#story`, `#code`, or any element id (`#code-chain` opens the
Code tab and scrolls there). Arrow keys / Home / End move between tabs.

## 9. Page mode (one scrollable document)

```
python assemble.py --page --toc --title "Backoff explainer" --overview overview.html   --section story=frag-story.html --section code=frag-code.html --out index.html
```

- Same fragments as tabs; every section is visible at once and `EV.onShow` fires for all of them at load.
- Each section is opened by a part heading (`header.ev-part-head#NAME`): eyebrow = number · `data-label` · `data-hint`,
  `h2` = `data-part-title` (e.g. "How the code changes"), optional `p` = `data-part-lede`. Set these on the fragment's `<section>`.
- `--toc` adds a sticky chapter list on the left (≥1160px) that collapses to a sticky top bar with a dropdown below that.
  Entries: Overview (`#overview`), one per section, plus a sub-entry for every element in the fragment with
  `id` + `data-toc="Short label"` (story scene groups, code steps, details). Active entry follows the scroll.
- Sticky things inside a fragment must sit below whatever is stuck to the top: use `EV.stickyTop()` (px; tab bar or
  chapter bar, 0 if none; also in CSS as `var(--ev-sticky-top)`), and re-measure on resize.
- Side panels (story graphic, code panel, preview) go on the **right**, text on the **left**, and the panel is
  stuck in the **vertical centre** of the viewport below the top bar. Use `ev-side` + `ev-stick` for this.
