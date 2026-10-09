---
name: explainer-kit
description: Use when building or assembling an explainer page with `explain-visually` or any `explain-with-*` skill, to get the shared themes, components and assembly script so every explainer looks the same.
---

# Explainer Kit

The shared look and plumbing for all explainer pages. The `explain-with-*` skills say *what* to show; this kit
decides *how it looks* and *how the parts fit together*, so every explainer is consistent and no agent has to
invent CSS, colours or players.

## Use this skill when

- Building a chapter with any `explain-with-*` skill (storytelling, code walkthrough, preview, section clips,
  slides, video).
- Assembling several chapters into one page for `explain-visually`.
- Changing the explainer themes or adding a shared component.

## Files

All in `assets/` next to this file:

| File | What it is |
|---|---|
| `kit.css` | Design tokens (themes), type scale, spacing and every shared component, prefixed `ev-` |
| `kit.js` | Theme switcher, chapter list (TOC), tabs, code-block builder with highlighting, clip player (`EV.clip`), `EV.onShow` / `EV.onHide`, `EV.stickyTop()` |
| `shell.html` | Page template used by the assembler |
| `assemble.py` | Builds the final page from an overview and fragments, and validates the contract |
| `FRAGMENT-CONTRACT.md` | The rules every fragment follows, plus a component cheat sheet. **Read it before writing a fragment.** |

## Themes

- Four themes: **Violet** (default; dark-first, near-black with one violet accent, Geist type), **Ocean**,
  **Amber** and **Aurora**, each with a light and/or dark variant. The viewer can switch; the choice is remembered.
- Choose a first-load theme with `assemble.py --theme`. Don't add per-page palettes or fonts.
- Colours, fonts and radii come only from `var(--ev-…)` tokens, never literal values, because the page must
  work in every theme and in light and dark.
- Semantic colours have fixed meanings and always come with a glyph: new `+`, removed `−`, risk `!`,
  decision `◆`, ok `✓`. The accent marks "this is the point", not status.

## How a page is built

1. Each chapter is one **fragment**: a single `<section class="ev-tab-content" data-tab="NAME">` with its own
   scoped `<style>` and an IIFE `<script>` that builds inside `EV.onShow(NAME, …)`.
2. The coordinator writes the **overview** (`<header class="ev-overview">`): eyebrow, a headline that states the
   answer, one sentence, one hero visual, one key line with at most one "Decide" callout. No grid of info boxes.
3. `assemble.py` inlines the kit, inserts the overview and fragments, and refuses to write the page if a
   fragment breaks the contract.

```bash
# One scrollable page with a sticky chapter list (default for explain-visually)
python assets/assemble.py --page --toc --title "Short name" --overview overview.html \
  --section story=frag-story.html --section code=frag-code.html --section decide=frag-decide.html \
  --out index.html

# One fragment on its own page
python assets/assemble.py --standalone frag-slides.html --title "Short name" --out index.html
```

- `NAME` in `--section NAME=FILE` must equal the fragment's `data-tab`.
- Set `data-label`, `data-hint`, `data-part-title` and `data-part-lede` on the fragment's `<section>` for the
  chapter heading; give elements `id` + `data-toc="Short label"` to list them in the chapter list.
- The output is one self-contained HTML page, ready to publish as an artifact.

## Shared rules for every chapter

- Concise first: takeaway headline → one concrete visual → at most 2–3 short sentences → details.
- Details sit behind `ev-more` toggles whose summary **names what they contain** (e.g. "Tick trace · Why 5 rows").
  Never show a bare "More" or "Show details".
- Make details visual too: highlighted code lines, diff gutter, groups, status chips, compact tables, small bars.
- Text meant to be read is never faded or hidden while it is on screen.
- Motion explains something or it goes. Respect `prefers-reduced-motion`; a page must be complete at rest.
- Keep everything in one page. Don't link between separate pages inside one artifact.

## Changing the kit

- If a chapter needs a component the kit lacks, add it to `kit.css` / `kit.js` (with the `ev-` prefix) and the
  cheat sheet in `FRAGMENT-CONTRACT.md`, instead of styling it inside one fragment.
- Re-run `assemble.py` on an existing page afterwards to check nothing broke.
