---
name: explain-with-storytelling
description: Use when asked to explain visually with storytelling.
---

# Explain with Storytelling

A scroll-driven story ("scrollytelling"): short text steps on the left scroll past one sticky graphic on the
right, held in the vertical centre of the viewport. As each step scrolls into view, the graphic changes to show
it. Best for giving the big picture before the details.

## Use this skill when

- The user asks for a visual explanation of changes with storytelling.
- Used by an orchestrator to explain changes visually with storytelling.

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

- Fully readable from the moment they enter until they're nearly out of view. Never dim inactive steps; the
  current one gets a mild marker (the kit's `ev-step.is-active`: accent edge and a faint tint).
- Larger text than body copy, high contrast, short lines.

## Motion

- Transitions between states are short (≈300–800 ms) and explain the change: things grow, slide in or get struck
  through. No decorative motion.
- With reduced motion, swap states instantly.
- The page must look complete before any scrolling (the first step's state is visible at rest).
- The graphic's first state belongs to step 1 and must not change while step 1 is current: no intro state, no
  build-up as step 1 reaches the middle. The first change happens when step 2 becomes current.
- Scrolling back up restores the earlier states exactly: each state is set from the step number alone, never
  built on top of the previous state.

## Building it

- Build it as a fragment with the `explainer-kit` skill (tokens, `EV.onShow`). Lay it out with the kit's
  `ev-side` (steps left) + `ev-stick` (graphic right, sticky and vertically centred below the top bar). The first
  step starts at the top of its column, level with the graphic (no top padding or spacer); add bottom padding so
  the last step can reach the middle. Make steps `ev-step` boxes and drive them with
  `EV.steps(steps, function (i) { graphic.dataset.step = i + 1; })` (not an `IntersectionObserver`, which gets
  the reverse scroll wrong); key the graphic's states in CSS on the `data-step` attribute.
- Give scenes `id` + `data-toc` so they appear in the chapter list.
- Check with screenshots at several scroll positions (Playwright, or a page that forces each step).
