---
name: explain-visually
description: Use when the user asks for a visual explanation or to 'explain visually'.
---

# Explain Visually

The goal: the reader quickly understands what changes, how it works and why, and can decide, without reading
every line of code. Show rather than tell, concise first, details on demand. One page, ~1,000–1,600 words.

The look comes from the `explainer-kit` skill; each chapter follows its `explain-with-*` skill.

## Use this skill when

- The user asks for a visual explanation, an explainer or "explain this visually".
- Explaining a code change, a proposal, a plan or an architecture decision so the user can make informed decisions.

## 1. Gather the facts into `facts.md`

- If a facts file already exists (e.g. the task gives you one), it is your source of truth: skip to step 2.
- Otherwise append each fact to `facts.md` in the working folder **as you find it**, one line with its source
  (`file:line`, link, or the command you ran). Don't restate facts in your thinking; write them down once.
- Get numbers from commands (`grep -c`, `jq`, a timed run), not by counting by hand.
- Measure on the real repo when it is cheap (a scratch copy or worktree, never the repo itself). Note method and
  versions. Never stretch one measurement into "every" or "all".
- Budget: at most 3 web searches and 3 page fetches; stop when every claim you plan to make has a source.
- Note what the user must decide, the effort per option, the risks with their fixes, and what would change the
  recommendation.

## 2. Plan the page (no separate brief)

Write the plan as the first lines of `notes.md` (≤ 15 lines): the one-sentence answer, the 3–5 key numbers (each
gets **one** home on the page), and one line per chapter. Chapters:

| Chapter  | Built with                                 | Section  | When                                                   |
| -------- | ------------------------------------------ | -------- | ------------------------------------------------------ |
| Overview | this skill (kit overview)                  | —        | always                                                 |
| Story    | `explain-with-storytelling`                | `story`  | always: 5–7 steps, one evolving graphic                |
| Code     | `explain-with-code-walkthrough`            | `code`   | only when the change *is* code the reader must see     |
| Decision | `explain-with-preview`, options (JSON)     | `decide` | when the user has something to decide                  |

- At most **3 chapters** after the overview. Fragility, dependencies and complexity go into the decision options'
  rows (keeps / loses / fix first / risks), not into chapters of their own. A separate before/after chapter
  (`explain-with-preview`) only replaces Code when there is no decision.
- **Overview:** a headline that states the answer and the trade-off, one sentence, one hero (to scale; for
  numbers use the kit's HTML `ev-bars ev-bars--hero`, which stays legible on phones), and one key line with at most
  one "Decide" callout. No grid of info boxes.
- Only add `explain-with-section-clips`, `-slides` or `-video` when the user asks for them.

## 3. Build the chapters yourself

- Read `explainer-kit/SKILL.md` and `explainer-kit/assets/FRAGMENT-CONTRACT.md`, then the chapter skills you use.
  **Never read `kit.css`, `kit.js` or `assemble.py`**: the contract is the whole API.
- Write the chapters yourself, one file each, in order. Don't start subagents for a page this size.
- Use kit components as they are; no new themes, fonts or components, and no layout CSS of your own.
- References go in the details: file paths in code headers, links in the decision's Sources toggle.

## 4. Assemble, check once, publish

```bash
python <kit>/assets/preview.py decide.json --out frag-decide.html
python <kit>/assets/assemble.py --page --toc --title "Short name" --overview overview.html \
  --section story=frag-story.html --section decide=frag-decide.html --out index.html
python <kit>/assets/check.py index.html
```

- Fix the contract errors the assembler reports.
- Run `check.py` once. Fix only the problems it lists, run it once more, then stop. Don't take or study
  screenshots to hunt for other issues and don't write your own browser scripts.
- Read your page text once against `facts.md`: counts, names, no "every/all" the facts don't support.
- Publish the single page as an artifact (unless told to just write the file).
