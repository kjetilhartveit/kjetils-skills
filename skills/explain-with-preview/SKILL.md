---
name: explain-with-preview
description: Use when the reader should compare two or more states by switching between them, such as the options of a decision or the before and after of a change's fragility, dependencies or complexity.
---

# Explain with Preview

A two-column chapter: a short takeaway and a few clickable cards on the left, and a sticky preview panel on the
right that switches when the reader picks a card. Switching back and forth makes the differences obvious.

## Use this skill when

- Presenting a **decision**: each option is a card, and the panel previews what that option means.
- Showing **before and after** for long-term effects of a change: fragility, dependencies, complexity.
- Any comparison where seeing two states in the same frame says more than describing them.

## Two modes

| Mode | Cards | Default selection | Extras |
|---|---|---|---|
| Options (decision) | One per option, usually 2–3 | The recommended option | A "Recommended" badge, 2–3 pro/con chips per option |
| Before / after | Exactly two: "Before · today" and "After · with the change" | After | No badge; each card has a one-line summary of that state |

## Left column

- One sentence that frames the question (decision) or the takeaway (before/after).
- The cards: clearly clickable, keyboard accessible (arrow keys), the selected one visibly highlighted.
- Keep it short. Detail belongs in the panel or in one `ev-more` toggle that names its contents.

## Preview panel

- Shows the **whole picture for the selected state** in a layout that stays identical between states, so only
  the differences change when switching.
- Mark what differs between states (an accent bar, a "changed" chip) and give the switch a short cross-fade.
  Respect reduced motion.
- Pick the content for the topic:
  - Decision: the code change for that option (or "no code change"), plus what happens in practice.
  - Fragility: every failure case as a row, with what the system does in that state and an outcome chip
    (fails safe, slows down, alarm reports it, needs a decision).
  - Dependencies: one small diagram of what depends on what; new edges and modules highlighted.
  - Complexity: the code each piece adds (empty slots before, `+` lines after) and a small tally, including
    what is *not* added.
- Use real content. If a visual has to be illustrative, label it as an illustration.

## Phones

- Show the panel inline under the cards.

## Building it

- Build it as a fragment with the `explainer-kit` skill; place the sticky panel below `EV.stickyTop()`.
- When several chapters use this pattern (e.g. fragility, dependencies and complexity), generate them from one
  template plus per-chapter data so they look like a series and are fast to produce.
