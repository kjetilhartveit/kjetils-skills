# Known problems

Concrete problems that earlier runs and their analysis reports found in pages made with `explain-visually`, each
with where it was seen and what was tried. They all apply to the skills on `main`: none of the earlier fixes were
kept. The full first attempt (runs, reviews, skill patches) is archived outside the repo in
`kjetils-skills archive/explain-visually-loop-2026-10/` (OneDrive).

Sources: **Q** = Qwen run (`02-qwen-session-analysis.md`), **B** = Opus baseline (`01-baseline-analysis.md`),
**H** = Haiku runs, **O** = Opus harness check, **S** = Sonnet runs, **cp1–3** = whole-page checkpoints (Opus,
Sonnet and Haiku) in the first attempt. "Tried" says what the first attempt did and how it went.

## Checking the page

| # | Problem | Seen in | Tried |
| - | ------- | ------- | ----- |
| 1 | No easy way to check the page: agents write their own screenshot scripts (5 in one Opus run), loop on them (Q: ~60k tokens, 47% of the run, mostly arguing with screenshots), or skip the check | Q, H, O, S | A kit `check.py` (screenshots plus a list of measured problems, re-run at most once). Found every recorded defect on 10 old pages; agents used it, but a chapter agent still ran its own browser checks for 13 min / 74k tokens (cp3) |
| 2 | Layout defects ship unnoticed: sticky panels taller than the screen, tables clipped inside sticky panels, sideways code, the page scrolling sideways on phones | Q, O, S | Detected by `check.py` |
| 3 | Text unreadable on phones: scaled-down SVG heroes and diagrams at 5–7 px | B, O, S | Detected by `check.py`; no fix for the hero itself |
| 4 | Defects that only appear in later story states: clipped content, overlapping labels, the current step hidden under the pinned phone graphic, a pinned graphic that scrolls inside itself | Q, S | `check.py` stepping through every story state |
| 5 | Opening a toggle on a phone makes the page scroll sideways (a long unbreakable path) | cp3 | Not tried |
| 6 | Tables scroll sideways on phones, hiding decision and risk columns | S, cp1–3 | Not tried (idea: a kit table that stacks rows as cards on phones) |

## Research and facts

| # | Problem | Seen in | Tried |
| - | ------- | ------- | ----- |
| 7 | Candidates never run: claims from web summaries, no measured numbers, no sources | S, H | "Measure, don't just search" with a recipe and a `measure.py` timer. Research briefs went from 22 to 31/40 (Sonnet) and every checkpoint number was measured, but runs got 2–3× more tokens and pages got longer (cp3) |
| 8 | Measuring is fiddly and slow: retries on migrator and config paths, `.mts` configs, line endings; ~70% of a run's time | S | The recipe above |
| 9 | A long command hung (ESLint), went to the background and the session idled ~3 h | S | Each measurement capped at 300 s, one command per call |
| 10 | `node_modules` symlinked into a throwaway worktree, then deleted through the link | O | "Install in the copy; never symlink from the real checkout" |
| 11 | Wrong or overstated numbers: grep counting generated files, captions claiming more than was timed, mixed denominators, timing from a failing run | H, S, cp3 | Count with git-tracked files; say what each number covers |
| 12 | Temporary files written into the project during measuring; tools run in the user's checkout | S | Configs in the copy, passed with flags |
| 13 | Lint timed before code generation (fails with 95 errors); a `cp -r` of the checkout with `node_modules` took 10 min | cp3 | Not tried (idea: run the project's prep steps and one passing run first) |
| 14 | Out-of-date web claims ("type-aware oxlint is alpha") and one crashing rule generalised to a whole plugin, with the recommendation resting on it | cp3, research briefs | Not tried (idea: check source dates; isolate the failing rule before concluding) |
| 15 | Weak models can run out of time measuring: Haiku hit a 25-min cap with no answer and left its worktree behind | H | Not tried |
| 16 | No sources or versions on the page for web claims | S | Not tried |

## Building the page

| # | Problem | Seen in | Tried |
| - | ------- | ------- | ----- |
| 17 | Phone pin of the story graphic hand-built per fragment (Q's single biggest sink) or broken (graphic after all steps) | Q, S | A kit class `ev-side--pin` |
| 18 | Chapter skills not loaded: a story without steps or sticky graphic, tables instead of evolving visuals | H, S, cp3 | A ready-made story template; Sonnet still skipped the storytelling skill at cp3 |
| 19 | Story graphics uniform: with a template, agents relabel its example graphic; without one, hand-built graphics break more | S, cp2, cp3 | Calling the example "wiring only" and asking for the mechanism raised originality from 3.5 to 7.5/10 (Opus) in isolation, but the coordinator then prescribed the graphic in its subagent prompt (cp3) |
| 20 | No ready-made before/after or decision chapters: each run re-implements cards, panels and keyboard JS (3× in one run); Opus writes 13–20k-token generators that make near-identical tables | S, cp2 | Not tried |
| 21 | Kit docs misread: doubled chip glyphs (the kit adds them), unscoped overview CSS (7 assembler errors), guessed `ev-bars` markup, "tab" wording confusing page mode | S | Cheat-sheet fixes; the failures disappeared |
| 22 | The kit's path is a placeholder (`<explainer-kit>`); one run never found the kit | H | State where the kit lives |
| 23 | Weak models skip the kit and hand-write the whole page with their own theme | H, cp2, cp3 | Not tried (idea: load the kit first; done means assembled) |
| 24 | Every chapter agent re-reads `kit.css` / `kit.js` (~200k cached input each) | O | Not tried |
| 25 | A failed multi-file bash heredoc lost every file in it (8–13k tokens, ~30% of a run) | S | "Write files with the file-write tool, not heredocs"; the failures disappeared |
| 26 | The chapter list highlights the previous scene when a new scene's first step is current | S | Not tried |

## The page as a whole

| # | Problem | Seen in | Tried |
| - | ------- | ------- | ----- |
| 27 | Too long and repetitive: 2,300–2,700 words, key numbers repeated 5–9 times, the same table 3–4 times, 6 chapters | B, O, S, cp3 | Not tried (idea: one home chapter per fact, word budget, 3–4 chapters) |
| 28 | No real code or config snippet on a proposal page | S | Not tried |
| 29 | Coordinator prompts to chapter agents are long and custom, and prescribe designs | Q, cp3 | Not tried (idea: a fixed prompt template: facts and the point, no design) |
