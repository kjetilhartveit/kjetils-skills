---
name: explain-with-slides
description: Use when the reader wants a quick, high-level grasp of something as a short deck of slides, one idea per slide, without details.
---

# Explain with Slides

A short deck of high-level slides: one idea per slide, a headline that is the takeaway, one big visual. For an
overall grasp, not for details.

## Use this skill when

- Someone asks for slides, a deck or a quick high-level summary.
- The audience needs the gist in under a minute, e.g. before a meeting or for stakeholders.

Not the default for explaining a change: details, code and tables don't belong in slides.

## Content

- 5–8 slides. Each: a headline that states the takeaway, one big visual, at most ~20 words of supporting text.
- No code, no tables, no detail slides, no details drawer. If the reader needs more, the last slide can point to
  the full explanation.
- Order: the problem → the change → the result → what's left to decide.

## Navigation

- When slides are part of a scrolling page, stack them **vertically** so the scroll direction stays the same as
  the rest of the page. Avoid horizontal paging inside a vertical page.
- A standalone deck may page sideways with keyboard, swipe, dots and prev/next buttons, with a deep link per slide.
- Subtle entry animations on each slide (bars grow, items rise); text never fades. Respect reduced motion.

## Building it

- Build it with the `explainer-kit` skill, usually as a standalone page (`assemble.py --standalone`).
