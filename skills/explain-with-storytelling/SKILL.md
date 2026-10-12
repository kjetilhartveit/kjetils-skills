---
name: explain-with-storytelling
description: Use when asked to explain visually with storytelling.
---

# Explain with Storytelling

A scroll-driven story: short text steps on the left scroll past one sticky graphic on the right. As each step
reaches the middle, the graphic changes to show it. On phones the kit pins the graphic at the top and the steps
scroll under it. Best for the big picture before the details.

## Use this skill when

- The user asks for a visual explanation of changes with storytelling.
- Used by an orchestrator to explain changes visually with storytelling.

## Story

- 5–7 steps, 1–2 short sentences each, one idea per step. Explain jargon in a few words the first time.
- An arc: the situation today → what goes wrong or costs → the change → the result → the catch or risk.
- **One graphic** (one SVG) that evolves through all steps: things appear, get highlighted, struck or counted.
  Not a dashboard of every fact at once, and not a different picture per step.
- Concrete and to scale (real times, real counts); label things on the graphic itself; one big number that
  updates with the story helps.
- Don't repeat the overview's numbers in every step, and don't append a details block; it ends when the story ends.

## Build it (no script, no layout CSS)

```html
<section class="ev-tab-content" data-tab="story" data-label="Story" data-hint="6 steps" data-part-title="…">
<div class="ev-side ev-side--pin" data-ev-story>
  <div>
    <div class="ev-step" id="story-today" data-toc="Today"><b>Today:</b> one or two sentences.</div>
    <div class="ev-step">…</div>
  </div>
  <div class="ev-stick"><figure class="ev-visual"><svg class="ev-svg" viewBox="0 0 440 320" role="img" aria-label="…">
    <text x="20" y="44" class="ev-t-lg" data-say="44.0 s|5.3 s||3.3 s">44.0 s</text>
    <rect x="20" y="70" width="400" height="28" rx="4" class="ev-f-line" data-hl="1"/>
    <rect x="20" y="110" width="48" height="28" rx="4" class="ev-f-acc" data-on="2-" data-hl="2,5"/>
    <text x="20" y="180" class="ev-t-risk" data-on="3">! what goes wrong</text>
  </svg></figure></div>
</div>
</section>
```

- The kit wires `data-ev-story`: for step n it sets `data-step="n"` on the panel and, inside it, shows
  `data-on` elements only on their steps (`2-4`, `3-` = from 3 on, `2,5`), adds `.is-hl` on `data-hl` steps and
  sets `data-say` text to the n-th item (`a|b||d`; an empty item keeps the previous text). Step 1's state is what
  the page shows at rest; scrolling back restores states exactly. Use only these attributes and the kit's SVG
  classes; add a scoped `<style>` keyed on `[data-step="3"]` only for what the attributes can't express.
- Bars and blocks are filled rects (`ev-f-acc` the point, `ev-f-new` good, `ev-f-risk` bad, `ev-f-line` neutral,
  `ev-f-sunken` track); boxes in a diagram are `ev-node` (+ `is-acc`, `is-new`, `is-risk`), arrows `ev-wire`.
  `data-hl` outlines a rect or accents a node / text.
- `ev-side--pin` spaces the steps and pins the graphic on phones; don't add padding, spacers or media queries.
- Keep the SVG compact so it stays legible when pinned on a phone: `viewBox` about 440 × 300 (at most 480 wide),
  labels at the kit's default size (15) or larger, no labels smaller than `ev-t-xs`.
- Give the first step of each scene `id` + `data-toc` so it shows in the chapter list.
