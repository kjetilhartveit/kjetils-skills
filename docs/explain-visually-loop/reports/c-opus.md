# Optimizer C (Opus): A's speed, plus glosses, one real snippet and kit layout fixes

Branch `ev-opt/c-opus`, built on A's final skills (`ev-opt/a-opus`, `a-v3`). Every run is Sonnet or Haiku in `facts`
mode, scored with the converged `tools/score.py` (blind Opus judge, one judgement per run). I had a smaller budget
than planned: 4 Sonnet runs (2 candidates × 2) and 1 Haiku run. The final candidate is `c-v2` (commit `7ab5db6`).
`c-opus/` holds the better-scoring of its two Sonnet runs (`075753`).

## Results

The reference rows come from the brief and use the same converged scorer. Output tokens are the GX10-minutes
proxy (÷ 900 ≈ minutes at 15 tok/s).

| label | run | overall | quality | checks | judge | speed | economy | out_tok | wall_s | turns | cost | words | chapters |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (ref., mean of 4) | | 68.4 | 69.2 | | 65.9 | 61.0 | | 27.8k | 183 | 17 | | 1,550 | 4–5 |
| A `a-v3` (ref., mean of 2) | | 85.8 | 82.8 | 100.0 | 73.5 | 88.1 | | 11.3k | 79 | 13 | | 950 | 2 |
| A `a-v3` Haiku (ref.) | | 80.6 | 80.4 | | 69.8 | 71.6 | | 25.0k | 151 | 13 | | 1,039 | 2 |
| c-v1 | 20261013-075408-sonnet-facts | 84.7 | 84.3 | 100.0 | 75.8 | 79.1 | 95.6 | 15850 | 100 | 14 | 0.40 | 1125 | 2 |
| c-v1 | 20261013-075414-sonnet-facts | 89.2 | 88.6 | 100.0 | 82.5 | 87.2 | 95.1 | 12173 | 85 | 11 | 0.33 | 1201 | 2 |
| **c-v1** | **mean of 2** | **87.0** | **86.4** | **100.0** | **79.2** | **83.2** | **95.3** | **14011.5** | **92.5** | **12.5** | **0.36** | **1163** | **2** |
| c-v2 | 20261013-075753-sonnet-facts | 87.3 | 86.0 | 100.0 | 78.5 | 85.5 | 95.3 | 12216 | 92 | 13 | 0.34 | 1196 | 2 |
| c-v2 | 20261013-075759-sonnet-facts | 86.0 | 83.8 | 100.0 | 75.0 | 85.9 | 95.4 | 11649 | 89 | 14 | 0.34 | 1122 | 2 |
| **c-v2 (final)** | **mean of 2** | **86.7** | **84.9** | **100.0** | **76.8** | **85.7** | **95.3** | **11932.5** | **90.5** | **13.5** | **0.34** | **1159** | **2** |
| c-v2-haiku | 20261013-080053-haiku-facts | 81.8 | 85.4 | 100.0 | 77.5 | 64.8 | 95.7 | 32726 | 150 | 14 | 0.03 | 1128 | 2 |

Judge items, the mean of all 4 C runs against A's 2 (v1 and v2 differ only in the story wording, one skill line and
a CSS padding):

| | headline | accuracy | evidence | story | decision | concision | clarity | phone | desktop |
|---|---|---|---|---|---|---|---|---|---|
| A `a-v3` | 7.5 | 7.5 | 7.5 | 7.5 | 8.5 | 7.5 | **4.5** | 8 | 7 |
| C (v1 + v2) | 8.0 | 8.0 | 7.75 | **6.5** | 8.75 | 7.75 | **7.75** | 8 | **7.75** |

What the numbers say:

- **Quality goes up by 2–3.6 points, and output tokens stay the same.** c-v1 reaches 86.4 quality (target ≥ 86) at
  14.0k tokens. c-v2 reaches 84.9 at 11.9k, which is A's token level (11.3k). Pooled over all 4 runs, quality is
  85.7 and overall 86.8, against A's 82.8 / 85.8. Within one candidate the judge's score ranges from 75.0 to 82.5,
  so the gap between v1 and v2 is noise.
- **Clarity, the judge's main complaint about A, is fixed:** 4.5 → 7.75. Jargon is glossed where it first appears,
  and two real snippets (the 2-line shim and `.oxfmtrc.json`) appear in the option panels. The cost is
  ~0.5–1k tokens.
- **Accuracy and headline go up a little** (7.5 → 8). No run repeated A's "263 rules keep working" or the
  "React rules run as JS plugins" error. Every headline now states the cost ("with 1 rule switched off and
  3 path checks to port"). The judge still finds one or two small slips per page, most often attaching the
  git count of 856 files to the run-1 timings.
- **Desktop goes up** (7 → 7.75; 8 in every v2 run). The decision panel is now level with the first card, and
  "What would change this" fills the empty space under the cards.
- **The story got worse** (7.5 → 6.5) and is now the weakest item. See "What I'd do next".
- **Haiku:** 85.4 quality against A's 80.4, overall 81.8 against 80.6. The run generated 32.7k tokens, and 23.9k
  of those were Haiku's own thinking. The work itself was lean: 4 writes, 2 builds, 1 small edit and 14 turns.
  This is a single run, so how much Haiku thinks is mostly noise.
- The deterministic checks score 100 in every run (all facts, no layout problems, full structure).

## What changed and why

### Accuracy and headline (rules in `explain-visually`)

- "Say exactly what the facts say, above all in the headline" is now four short rules, each with an example:
  - "migrated" is not "kept" or "working", and exceptions go in the same sentence;
  - a number measured under changed conditions is not "the same" ("5.3 s, after switching that rule off");
  - what holds for some members doesn't hold for the group (name them);
  - gloss each term the first time it appears.
- The headline states the answer **and its main cost**, and the plan records that cost on its first line.

### Clarity (glosses plus one real snippet, no code chapter)

- The plan in `notes.md` now lists the 4–8 terms to gloss and the one real snippet to show. Writing them down up
  front made Sonnet and Haiku gloss tsgolint, JS plugins, nursery and GritQL in every run.
- `preview.py` takes an optional `"code": {"file", "lines": [...], "add"/"del"/"hl"}` per option. It renders a
  kit `ev-code` under the option's rows. The code is given as a list of lines because a weak model handles that
  more reliably than escaped `\n` strings in JSON. Every run used it for the shim and/or `.oxfmtrc.json`. That
  costs about 150 tokens, against ~5k for B's separate code chapter.
- New kit modifier `ev-code--wrap` (used by `preview.py`): long lines wrap instead of scrolling sideways, so
  snippets in the narrow option panel never trigger the "code scrolls sideways" layout check.
- `explain-with-preview`: gloss a term in the row where it first appears, and "How it was measured" lists the
  commands as well.

### Desktop layout (kit, zero tokens)

- `initSide` (kit.js): a panel taller than its first text box is now top-aligned with it instead of centred on
  it. Before, it started above the first story step or option card, which the judge flagged on A's page. I took
  this idea from B.
- `preview.py` + kit.css: "What would change this" moved into the cards column, so the space next to the tall
  panel is filled. On phones a `display: contents` + `order` rule keeps the reading order as cards → panel →
  callout. The pick panel is no longer a scroll box (`max-height: none`), so a code snippet can't make it
  "cut off".
- Story tail: the step column's bottom padding went from 30vh to `max(s5, panel height / 2 − 25vh)`. That is
  just enough for the panel to stay in view while the last step reaches the middle, and the page is ~180 px
  shorter. The judge still names the "empty band after the story" in some runs, because the 12vh gaps between
  steps also add space. All layout checks still pass, including the per-step panel-in-view check.

### Story graphic (`explain-with-storytelling`)

- A copyable SVG template replaces the abstract example. It has a counter (`ev-t-num`), to-scale rows whose empty
  tracks show from step 1 (so the panel is never a small drawing in a big empty box), right-aligned values and
  a caption line with one `data-say` item per step.
- New rules: every step changes something visible; bars on one scale share a unit and base (the judge flagged A
  for drawing 263/276 against 163/295); the SVG text classes are listed in the contract (`ev-t-num` is only for
  the one counter, a misuse B found).
- c-v2 added "don't redraw the hero; show the thing the numbers are about and draw the catch on it". That
  backfired somewhat. Both v2 stories became rule-count bars, and the judge then said the speed problem never
  appears in the story and that the empty tracks at step 1 "look unfinished". The template removed the
  emptiness, but it still invites "a dashboard filling in", which is what the judge marks down (story 6–7).

### What the model reads, and wasted turns

- `FRAGMENT-CONTRACT.md` is now page-mode only, 12.6 KB → 10.2 KB. Script rules, `EV.clip`, `EV.steps` and tab mode
  moved to a new `SCRIPTS-AND-TABS.md`, which only the code-walkthrough, clips, slides and video chapters need.
  `explain-visually` says to read the contract and the chapter skills in one turn and never the scripts file.
  The runs still read `explainer-kit/SKILL.md` (4.5 KB), because the harness prompt tells the model to read
  any skill that is mentioned.
- One c-v1 run tried to write all five files in a single 13.9k-character bash heredoc. It failed on a quote, and
  every file was written again with Write, which cost ~4k tokens (15.9k in total). c-v2 says to use the Write
  tool per file and never a heredoc, and to run the build only after every write has returned, as one chained
  command. Neither v2 run repeated the waste, and neither fired the build before the writes finished.
- The final reply is capped at 5 lines (A's replies were 1.3–2k characters).

## What I'd do next

1. **Story graphic with a cause and a consequence.** This is now the weakest criterion, and prose rules haven't
   fixed it in two rounds. Both phase-1 reports and this one point to the same fix: generate the story graphic
   from data, the way `preview.py` generates the decision. For example, `story.json` would list rows/boxes with
   per-step states, and a kit script would draw a to-scale, frame-first SVG with a step caption. Two layouts
   would cover most stories: "race" (bars with a counter) and "pipeline" (boxes that get swapped and break). This
   would also take ~1k tokens of hand-written SVG off a weak model.
2. **Undo the "don't redraw the hero" line** or soften it: "the story may reuse the hero's numbers, but each step
   adds the cause or the consequence". I had no runs left to test it.
3. **Facts-mode accuracy nits** are mostly one mistake: putting the 856-file git count on the run-1 timings.
   That's a facts-file ambiguity more than a skill problem. In full mode the facts ledger records counts with
   their measurement.
4. Spend 2 more Sonnet runs on the final candidate. Single-run judge scores range from 75 to 82.5, so 2 runs per
   candidate can't separate v1 from v2.

## Disagreements with the scorer

- **Judge variance dominates.** Two runs of the same candidate differ by up to 7.5 judge points (5 points of
  overall). A `--judge-runs 2` average on the final runs would help, but I didn't have the budget for it.
- **Empty frame vs "unfinished".** The rubric (and A's critique) penalise a small graphic in an empty panel at
  rest, but the judge also calls empty tracks at step 1 "unfinished". Drawing the frame first is the usual
  scrollytelling practice. A story graphic can't win both ways, so the rubric's story text could say that a
  frame filled in step by step is fine.
- **Haiku's speed score is mostly Haiku's thinking** (23.9k of 32.7k output tokens) and says little about the
  skills. Reporting `output_tokens_total - thinking_tokens_total` next to the total would separate skill-driven
  generation from model verbosity.
- The scorer itself is unchanged.

## Files

- Skills: `skills/explain-visually/SKILL.md`, `skills/explain-with-storytelling/SKILL.md`,
  `skills/explain-with-preview/SKILL.md`, `skills/explain-with-code-walkthrough/SKILL.md`,
  `skills/explainer-kit/SKILL.md`, `skills/explainer-kit/assets/{FRAGMENT-CONTRACT.md, SCRIPTS-AND-TABS.md, preview.py, kit.css, kit.js}`.
- Final page and scores: `reports/c-opus/` (`index.html`, `measures.json`, `score.json`, `judge.json`, `result.json`).
