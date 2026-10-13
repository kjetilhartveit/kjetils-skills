# Optimizer A (Opus): smaller plan, kit components, check once

Branch `ev-opt/a-opus`. Sonnet stands in for Qwen, with one Haiku pair as the weaker proxy. All runs are in `facts`
mode and scored with `tools/score.py` (rubric in `../scoring.md`). The final candidate (`a-v3`, commit `9d7173a`)
is in `a-opus/`: `index.html`, `measures.json`, `score.json`, `result.json`.

## Results

Means of 2 Sonnet runs per candidate; Haiku is 1 run each. Output tokens are the GX10-minutes proxy
(÷ 15 tok/s ÷ 60 = minutes).

| Candidate | Overall | Quality | Judge | Checks (facts/layout/structure) | Speed | Economy | Output tok | Wall | Turns | Cost | Context | Words | Chapters |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline (Sonnet) | 73.8 | 71.7 | 70.5 | 35.4 / 10.8 / 27.9 | 76.3 | 91.5 | 27.6k | 169 s | 18 | $0.68 | 879k | 1,308 | 4–5 |
| a-v1 | 87.0 | 84.6 | 76.8 | 40 / 30 / 29.2 | 94.7 | 83.4 | 14.1k | 106 s | 13 | $0.37 | 409k | 821 | 2 |
| a-v2 | 88.4 | 86.7 | 79.8 | 40 / 30 / 29.6 | 94.1 | 85.7 | 14.8k | 102 s | 13 | $0.38 | 381k | 862 | 2 |
| **a-v3 (final)** | **90.7** | **88.0** | **81.5** | 40 / 30 / 30 | 97.4 | 90.6 | **11.3k** | **79 s** | 13 | **$0.33** | 370k | 950 | 2 |
| baseline (Haiku) | 62.6 | 63.8 | 66.0 | 33.8 / 4.0 / 22 | 61.9 | 80.0 | 37.7k | 176 s | 30 | $0.08 | 2,133k | 1,269 | 6 |
| a-v3 (Haiku) | 85.9 | 84.7 | 76.5 | 40 / 30 / 30 | 84.1 | 93.3 | 25.0k | 151 s | 13 | $0.03 | 311k | 1,039 | 2 |

Individual Sonnet runs, overall: baseline 73.5 / 74.1, a-v1 89.1 / 84.8, a-v2 87.7 / 89.0, a-v3 90.3 / 91.1.

What the numbers say:

- **Output tokens −59 %** (27.6k → 11.3k; ≈ 31 → 13 min at 15 tok/s), wall time −53 %, cost −51 %, context −58 %.
- **Quality went up, not down** (judge 70.5 → 81.5). Layout is now perfect in every candidate run (30/30), against
  9.6–12 for the baseline: phone story pinned, no cut-off panels, legible hero. The decision chapter went from 6–9 to
  9/10 with the judge in every v2/v3 run.
- **Haiku shows the over-production the Qwen run had**: the current skills give 6 chapters, 30 turns and 2.1M
  context. With v3 it is 2 chapters, 13 turns and a page scored 85.9 against 62.6. The skills hold up on a weaker
  model, which is the point of the exercise.
- Sonnet with the current skills did not reproduce the Qwen failure modes (no subagents, no screenshot loop; it
  simply never checked its page). Its waste was writing 4–5 chapters of hand-made HTML/CSS/JS and pages with
  layout bugs it never saw.

## What changed, by sink (ref. 02 §4)

### 1. Phone pinning and story wiring become kit features (02 #1, #6 overrides)

- `.ev-side--pin`: below 900 px the panel moves above the steps, sticks under the top bar, is capped at 42 vh (its SVG
  scales to fit) and the steps scroll under it; `EV.steps` reads the step below the pinned panel. It also spaces the
  steps on desktop, so fragments contain no layout CSS at all.
- `.ev-side[data-ev-story]`: the kit drives the steps and applies `data-on="2-4"`, `data-hl="3"`, `data-say="a|b||d"`
  inside the panel, set from the step number alone (reverse scrolling is correct by construction). A story fragment
  is now markup only: no script, no `EV.steps` wiring, no media queries. This removes the code where the Qwen run
  spent its 60k-token fix loop.
- `.ev-tab-content:has(.ev-side)` gets the full page width, so story and decision panels aren't squeezed into 720 px.
- `ev-bars--hero`: an HTML to-scale bar chart for the overview, legible at 390 px (the baseline's SVG hero labels
  were 5 px on phones).

### 2. A deterministic check with a stopping rule (02 #2, #5, #10)

- `explainer-kit/assets/check.py index.html` opens the page on desktop and phone, scrolls every step and prints only
  problems with a fix hint (overflow, cut-off panels or code, SVG labels < 9 px, panel out of view or covering its
  step, console errors). It ends with "OK: nothing to fix. Stop checking." or "Fix only these, run once more, then
  stop". Without Playwright it says to skip rather than write a script.
- The skill says: run it once, fix only what it lists, re-run once, no screenshot study, no own browser scripts.
  Every v2/v3 run got "OK" from its one completed check and stopped. Some runs fired the whole
  preview/assemble/check command in parallel with the file writes; it failed on missing files and was re-issued,
  which costs one turn.

### 3. Fewer, generated chapters (02 #3)

- Default plan: Overview + Story + Decision, at most 3 chapters, ~1,000–1,500 words. Fragility, dependencies and
  complexity become the option rows (Keeps / Loses / Fix first / Risks / Effort) instead of chapters that repeat
  each other.
- `explainer-kit/assets/preview.py decide.json --out frag-decide.html`: the decision (or before/after) chapter is
  written as ~5 KB of JSON and rendered with the kit's new `ev-pick` component (cards plus a switching panel, a "What
  would change this" callout, a "How it was measured · Sources" toggle). It needs no HTML, CSS or script, and its
  shape makes the model fill in effort, fixes and what would change the recommendation. That is where the judge's
  decision score comes from.

### 4. No brief, no subagents, facts ledger (02 #4, #6, #8)

- No content brief: a ≤ 15-line plan at the top of `notes.md` (answer, 3–5 key numbers each with one home, one line
  per chapter). Chapters are written by the coordinator in order; no subagents for a page this size.
- In full mode, facts go into `facts.md` as they're found, one line each with source; numbers come from commands, not
  hand counts. (Judged by reading only; facts mode skips this step.)
- "Say exactly what the facts say": "migrated" ≠ "kept", and exceptions go in the same sentence. This cut the
  "263 rules stay" overclaims the judge flagged in v1.

### 5. Budgeted research, never read kit internals (02 #5, #7)

- Research budget: at most 3 searches and 3 fetches; measure in a scratch copy when cheap; stop when every planned
  claim has a source. (Not exercised in facts mode.)
- `FRAGMENT-CONTRACT.md` opens with "this is the whole API: don't read kit.css, kit.js or assemble.py"; the kit
  SKILL's file table says the same; "change the kit" is now only for when the user asks. Baseline Sonnet grepped
  kit.css/kit.js in both runs; v2/v3 runs never opened them.

## The scoring system

`tools/score.py <run-dir | page.html>` writes `score.json`: `overall = 0.60 Q + 0.25 E·min(1, Q/80) + 0.15 S`. Q is
35 % deterministic checks (facts regexes and overclaims, layout from Playwright incl. per-step and phone label
checks, structure) and 65 % a blind Opus judge (headline, accuracy, numbers, story, decision, concision, visual),
which sees only the facts file, `page.txt` and screenshots in a temp folder. Calibration on the corpus: baseline-opus
67.5, opus-1 57.1, opus-2 48.9, qwen 32.3. Three judgements of one page: 70.3 / 69.7 / 70.0.

Bug found on the way: `innerText` skips hidden panels, so the judge first saw only the selected option of every
switchable chapter. `page.txt` now un-hides them, and all pages were re-scored.

## What I'd do next

1. **Run v3 on Qwen in full mode.** The parts facts mode can't test (facts ledger, research budget, the stopping rule
   under real slowness) only show there. Watch whether Qwen still opens kit.css and whether it follows the check
   output.
2. **Trim the read-in.** Skills plus contract plus facts are ~40 KB per run; the contract still documents tab mode
   and clips that `explain-visually` doesn't use. A page-mode-only contract (or a split) would cut prefill and
   compaction risk on the GX10.
3. **Story graphic quality** is the weakest judge criterion (6–8): stories tend to be "a dashboard filling in". A
   couple of graphic templates in the kit (to-scale bars, before/after pipeline, counter) as copyable SVG snippets
   would help weak models more than more prose.
4. **Words sit at ~950**, just under the 1,000 band. Fine by the judge (concision 8), but the economy band could move
   to 900–1,600 if the user agrees this length is right.
5. Tell the model to run the build command only after the writes return: several runs fired it in parallel
   with the writes and had to repeat it.
6. A `--judge-runs N` average and per-task `KEY_FACTS` files would let the scorer serve other prompts.

## Tools worth keeping

- **Keep in the kit:** `check.py` (deterministic, with a stopping rule), `preview.py` + `ev-pick` (decision chapters
  as data), `ev-side--pin` + `data-ev-story` (phone pinning and story states without script), `ev-bars--hero`.
- **Keep in the harness:** `tools/score.py` and the extended `tools/shoot.py` (per-step panel checks, phone label size,
  story screenshots, `page.txt` with hidden panels). Note that `shoot.py` and the kit's `check.py` share their layout
  checks on purpose: the harness must not change when a candidate changes the kit.
