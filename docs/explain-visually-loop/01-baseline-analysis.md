# Baseline analysis: Opus explainer for "ESLint + Prettier → Oxc or Biome"

Baseline: `inputs/baseline-opus-index.html`, made by Claude Code + Opus 5.5 in ~11 min (run in
`C:\git\fantasy-snooker`). Contrast: `inputs/qwen-index.html`, Qwen 3.8 27B, 4 h 25 min. Screenshots in
`shots/baseline-opus/`. The user's verdict on the baseline: good, guiding but not conclusive.

## Size facts (measured from the rendered body, scripts and styles excluded)

| Measure                       | Opus baseline                                   | Qwen                                                     |
| ----------------------------- | ----------------------------------------------- | -------------------------------------------------------- |
| HTML size                     | 115 KB                                          | 219 KB                                                   |
| Chapters (after overview)     | 3: story, deps ("Packages & config"), decide    | 6: story, code, fragile, deps, complex, decide           |
| Visible words (incl. SVG)     | ~1,300                                          | ~4,500                                                   |
| Scroll steps                  | 8 (story)                                       | 13 (7 story + 6 code)                                    |
| Option / before-after cards   | 2 + 3                                           | 2 × 3 + 3                                                |
| Visuals                       | hero bar chart (to scale) + 1 scorecard grid    | hero bars, story graphic, deps diagram, several bars     |
| Code blocks / tables          | 0 / 0 (scorecard is a CSS grid)                 | 18 / 6                                                   |
| `ev-more` toggles             | 1 ("How it was measured · Sources")             | 5                                                        |
| Chips                         | ~14 static (+ generated)                        | ~100                                                     |
| Source links                  | 4 (oxc.rs ×3, biomejs.dev)                      | 0 links (sources named as text only)                     |
| Page height desktop / phone   | 4,512 px / 6,391 px                             | — / 19,479 px                                            |
| report.json                   | no overflow, no errors, 0 sticky panels cut off | phone page 473 px wide on a 390 px viewport (overflow)   |

## What the baseline does well

- **Answers in the headline.** "Oxlint + oxfmt keeps almost every rule and runs 3–5× faster. Biome is faster
  still, but drops about half the rules." The reader has the trade-off before scrolling. The keyline adds
  263/276 vs 152/295 and one "Decide" callout.
- **Real evidence, not marketing.** It ran all three migration tools and timed them in a throwaway worktree
  of `main@babd8a63` (repo untouched), and says so in "How it was measured": versions, core count, method
  ("prettier --write first, then count files each formatter changes"), single wall-clock runs including
  `pnpm dlx` startup. Findings only measurement could give: the react-x rule that crashes on 185 files, the
  202 `eslint-disable` comments Biome ignores, Biome's migrator not reading `.mts` and picking the wrong
  quote style (it would have touched 822 files), Prettier not being enforced (146 files drifted).
- **Honest numbers.** The hero caption adds the counterpoint: with a warm `--cache` ESLint takes 2.2 s, so
  the 29 s only hurts cold/CI runs. Bars are to scale (16 px/s).
- **Decision support.** Three options including a low-risk middle path (C: oxfmt now, oxlint later) that
  the user would not have asked for. Each option has get / fix first / risk lists with concrete actions
  ("narrow the testing-library glob so it skips `test/e2e/**`", "pin exact versions, let Renovate bump").
- **Concise.** ~1,300 words for a three-way tool comparison. Story steps are 1–3 sentences. Chapters that
  didn't apply (code, fragility) were skipped instead of padded.
- **Scorecard as the story graphic.** One grid (rule family × tool) whose highlighted column/cells and big
  counter change per step ("185 files where one react-x rule crashes"). Status uses glyph + colour (✓ ! −).
- **Clean in both themes.** Light and dark screenshots look equally finished; no literal colours.

## What it does less well

- **The story is a tour, not a story.** Steps go today → Oxc facts → Biome facts; there is no
  "what goes wrong → change → result" arc, and the graphic is a table that lights up cells rather than a
  concrete picture that evolves. Readable, but closer to a guided table than scrollytelling.
- **Jargon without help.** "nursery", "tsgolint", "GritQL", "JS plugins (alpha)" appear unexplained in
  story steps; a reader new to Oxc has to guess.
- **Not conclusive.** It recommends A but does not size the work (hours, PR count, CI change) or say what
  would flip the decision; "143 rules lost" (Biome chip) vs "98 not implemented + 34 unknown" (panel) is
  not reconciled on the page.
- **Some repetition across chapters.** 202 comments appears 8×, 29.4 s 5×, 263 5×. Each use has a reason,
  but the decision panel re-lists story facts.
- **Phone.** The hero SVG scales down, so its labels are ~5 px and unreadable at 390 px. The story graphic
  is not pinned on phones (skill rule): all 8 steps come first and the scorecard after them, so the
  step ↔ graphic link is lost.
- **Desktop layout gaps.** Story and Packages panels are much taller than their first card, so at rest
  there is a large empty area left of the panel before the first step/card.
- **No real config shown.** A snippet of the generated `.oxlintrc.json` or the 2-line wrapper would have
  made "carries over unchanged" tangible; the page has zero code blocks.

## Contrast: Qwen page

- Same facts gathered (a POC in the repo, measured timings, 146 drifted files), but it **overclaims**:
  "every rule carries over" while the Opus run found a rule that crashes on 185 files; Biome was timed
  "no config", which is not comparable with configured ESLint. Different machine timings (65 s vs 29.4 s)
  are fine; unsupported universals are not.
- **Repetition:** "65 s" appears 23 times; nearly every story step and option ends on it.
- **Too much:** 3.4× the words, 6 chapters, 18 code blocks, 6 tables, ~100 chips. Fragility/complexity
  chapters restate the same facts.
- **Layout:** code panel is half width and its long lines are cut off on desktop; phone page overflows
  horizontally (473 px); its story graphic on desktop sits beside a mostly empty column.
- What it does better: explains why ESLint is slow, has a code walkthrough of the real config, a
  migration path checklist, and marks each claim measured (M) / documented (D).

## What we should strive for

1. Headline that states the answer and the trade-off; one to-scale hero that stays legible on phones.
2. Measure on the real repo when it's cheap (worktree, migration tools, timings) and state method and
   versions in a toggle; link sources. Never extrapolate a measurement into "every"/"all".
3. Recommend, include a cautious option, and make it conclusive: effort, risks with fixes, and what
   would change the recommendation.
4. ~1,000–1,800 words; each key number in one home, referenced, not restated in every step.
5. Story with an arc and one evolving graphic; short real code where it makes a claim concrete.
6. Pass the kit contract and the phone rules (graphic pinned, nothing cut off, no overflow) in both themes.
7. Do it in minutes, not hours: fewer chapters, fewer components, one screenshot pass.
