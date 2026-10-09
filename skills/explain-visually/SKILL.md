---
name: explain-visually
description: Use when the user asks for a visual explanation or to 'explain visually'.
---

# Explain Visually

The goal: the reader quickly understands what changes, how it works and why, without reading every line of code,
and can still dig into the details. Show rather than tell, concise first, details on demand.

This skill coordinates. The look comes from the `explainer-kit` skill and each chapter follows its own
`explain-with-*` skill.

## Use this skill when

- The user asks for a visual explanation, an explainer or "explain this visually".
- Explaining a code change, a proposal, a plan or an architecture decision so the user can make informed decisions.

## 1. Gather the facts

- Gather enough relevant information to back every statement: read the code, docs, plans and history.
  Facts over guesswork and opinions; substance over fluff.
- Collect references to source material (`file:line`, docs, links) and the real code snippets you'll show.
- Note any decisions the user has to make, and the long-term effects: fragility (what can break and when),
  dependencies (what now depends on what) and complexity (what's added or removed, and is it worth it).

## 2. Write the content brief

Write a short markdown brief in the scratchpad. It is the single source of truth for every chapter, so chapters
can be built in parallel and stay consistent:

- The one-sentence answer and the key numbers.
- Per chapter: what it must show, the facts, the real code (with paths), and sources.
- What is a fact and what is an illustration.

## 3. The page

One scrollable page with a sticky chapter list on the left. Chapters, in this order:

| #   | Chapter      | Built with                           | Section name | When                                       |
| --- | ------------ | ------------------------------------ | ------------ | ------------------------------------------ |
| —   | Overview     | this skill (kit overview component)  | —            | always                                     |
| 1   | Story        | `explain-with-storytelling`          | `story`      | always: the big picture                    |
| 2   | Code         | `explain-with-code-walkthrough`      | `code`       | when code changes                          |
| 3   | Fragility    | `explain-with-preview`, before/after | `fragile`    | when relevant                              |
| 4   | Dependencies | `explain-with-preview`, before/after | `deps`       | when relevant                              |
| 5   | Complexity   | `explain-with-preview`, before/after | `complex`    | when relevant                              |
| 6   | Decision     | `explain-with-preview`, options      | `decide`     | only when the user has something to decide |

- **Overview:** a headline that states the answer, one sentence, one hero visual (the most telling concrete
  picture, drawn to scale), and one key line with at most one "Decide" callout. No grid of info boxes.
- Skip chapters that don't apply instead of filling them. Don't repeat the overview inside the chapters.
- Only add `explain-with-section-clips`, `explain-with-slides` or `explain-with-video` when the user asks for them.
  Slides and video are usually separate pages.

## 4. Build the chapters

- Load the `explainer-kit` skill and read its `FRAGMENT-CONTRACT.md`. Use the kit as is: don't design new themes,
  fonts or components for one page.
- When subagents are available, build the chapters **in parallel**: one subagent per chapter, each given the brief,
  its `explain-with-*` skill, the kit path, its section name and an output file. Build the three before/after
  chapters together from one template plus data.
- Every chapter follows the kit's shared rules: concise first; details in toggles that name their contents;
  visual details (highlighted code, chips, compact tables); no faded text; motion only when it explains.
- Put references in the details: file paths in code headers, `file:line` and links in the toggles.

## 5. Assemble, check and publish

```bash
python <explainer-kit>/assets/assemble.py --page --toc --title "Short name" --overview overview.html \
  --section story=frag-story.html --section code=frag-code.html \
  --section fragile=frag-fragile.html --section deps=frag-deps.html --section complex=frag-complex.html \
  --section decide=frag-decide.html --out index.html
```

- Fix any contract errors the assembler reports.
- Check the facts on the page against the brief (claims, counts, file lists). Agents drift.
- Look at the page once (screenshot or artifact preview) in dark and on a phone width; fix what's broken.
  Don't iterate on polish.
- Publish the single page as an artifact.

## Keep it fast

- The kit, the chapter skills and the brief remove most of the work: agents only write content and visuals.
- Parallel chapters, one screenshot pass and no redesign keep a full explainer to a few minutes per chapter.
