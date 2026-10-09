---
name: explain-with-storytelling
description: Use when explaining how something behaves over time or why a change matters as a scroll-driven story, where a sticky graphic changes as the reader scrolls through short text steps.
---

# Explain with Storytelling

A scroll-driven story ("scrollytelling"): one sticky graphic on one side, short text steps on the other. As each
step scrolls into view, the graphic changes to show it. Best for giving the big picture before the details.

## Use this skill when

- Giving the overview of a change, an incident or a mechanism before the code.
- The point is a change in behaviour over time (before vs after, a failure building up, a value growing).
- A reader should get the idea without reading code.

Not for line-by-line code changes (use `explain-with-code-walkthrough`) or for comparing two states side by side
(use `explain-with-preview`).

## Structure

- 5–9 steps. Each step is 1–2 short sentences: one idea per step.
- **One graphic** that evolves through the whole story. Steps change its state (highlight, add, remove, count,
  move); they don't swap in unrelated pictures. Group steps into 2–4 scenes if the graphic changes a lot.
- Order: the situation today → what goes wrong → the change → the result → the consequences or risks.
- End when the story ends. Don't append a block of details at the end of the story; code, tables and traces
  belong in the code walkthrough or preview chapters.

## The graphic

- Concrete and to scale: real timelines, real counts, the actual steps of a process with the new one
  highlighted. Avoid abstract boxes-and-arrows when a concrete picture is possible.
- Big numbers that update with the story (e.g. a counter) help the reader keep track.
- Label things on the graphic itself instead of using a separate legend.
- On phones, pin the graphic at the top and scroll the step cards under it; keep labels legible at 390px.

## Text steps

- Fully readable from the moment they enter until they're nearly out of view. Never dim inactive steps; mark
  the active one with a border or accent instead.
- Larger text than body copy, high contrast, short lines.

## Motion

- Transitions between states are short (≈300–800 ms) and explain the change: things grow, slide in or get struck
  through. No decorative motion.
- With reduced motion, swap states instantly.
- The page must look complete before any scrolling (the first step's state is visible at rest).

## Building it

- Build it as a fragment with the `explainer-kit` skill (tokens, `EV.onShow`, `EV.stickyTop()` for the sticky
  offset). Use `IntersectionObserver` with a trigger line near the middle of the viewport to set the active step,
  and drive the graphic's states from CSS keyed on a `data-step` attribute.
- Give scenes `id` + `data-toc` so they appear in the chapter list.
- Check with screenshots at several scroll positions (Playwright, or a page that forces each step).
