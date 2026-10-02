---
name: explain-visually
description: Use when the user asks for a visual explanation.
---

# Explain Visually

The goal: the reader quickly understands what changes, how it works and why, without reading every line of code. Be concise and show rather than tell.

## Use this skill when

- The user asks for a visual explanation.

## Structure of an explanation

1. Summary:
   - Start with a short summary of what changes and why.
   - Mention any important architectural or long-term considerations that the user should be aware of.
   - Keep it concise and easy-to-understand, details will be explained in the following steps.
2. Explain every concept/feature/change in two layers.
3. Explain architectural and long-term considerations in two layers. Consider at least the following aspects:
   - Fragility: what can easily break, and under which conditions.
   - Dependencies: new or changed dependencies, and what now depends on what.
   - Complexity: added or removed complexity, and whether it is worth it.

### Explaining in two layers

When explaining a concept/feature/change/architectural consideration in two layers, then do the following:

- Top level: concise, easy to understand, pseudo code, diagrams, visual effects etc.
- Concrete: actual code examples from the codebase (or the proposed code).

## Tips for effects/explanation methods

- Before and after: show the state before and after the change, side by side where possible, and why the change is needed.
- Include concrete examples.
- You may use animations.
- Pick the most fitting visual communication method which best explains the specific feature or concept.
- You may use prototypes or simulators to showcase the proposed solution when reading about it is not enough, e.g. for algorithms, UI behavior or state machines.
