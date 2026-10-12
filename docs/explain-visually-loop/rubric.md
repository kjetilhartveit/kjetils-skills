# Explainer quality rubric

Use this to score an explainer page made with the `explain-visually` skill. Score each criterion 1–10 against
the anchors, then check the hard failures. Scores are relative to the Opus baseline
(`inputs/baseline-opus-index.html`, see `01-baseline-analysis.md`), which sits at about 8 on most criteria.
A 10 means clearly better than the baseline, not perfect.

## How to verify

1. Read the HTML and the visible text. Note the question the user asked.
2. Run `python tools/shoot.py <page.html> <out-dir>` and look at every PNG plus `report.json`. Also look at
   the story/code panels at a few scroll positions and the full page at phone width (390 px).
3. Check numbers against the run's evidence (transcript, commands, sources) where available. Spot-check at
   least 5 key claims. If you can't verify a claim, say so; don't assume it's true or false.
4. Score, list hard failures, then add your own taste notes (see the end).

## Criteria

### 1. Answers the question

The overview tells the reader the answer before they scroll.

- **3:** Headline names the topic, not the answer ("Exploring linters"). Overview is a grid of boxes or
  needs the chapters to make sense.
- **6:** Headline gives an answer but no trade-off or key number; hero visual is generic or not to scale.
- **9:** Headline states the answer and the main trade-off with a key number; one-sentence lede; one
  to-scale hero that shows the core comparison; keyline with at most one Decide callout.

### 2. Factual grounding and evidence

Claims are backed by real measurements, code or sources, and nothing is invented or overstated.

- **3:** Numbers without provenance, generic marketing claims, or claims that contradict the evidence.
- **6:** Mostly sourced, but some unverified numbers, mixed-condition comparisons (e.g. configured vs
  default tool) or universals ("every rule carries over") the evidence doesn't support.
- **9:** Key numbers measured on the real project or linked to sources; method, versions and conditions
  stated (toggle is fine); caveats shown next to the number (e.g. warm-cache time); illustrations labelled.

### 3. Insight and decision support

The page helps the reader decide or understand, beyond listing facts.

- **3:** Facts listed without interpretation; no recommendation where a decision is pending.
- **6:** A recommendation with pros/cons, but generic, or missing the risks, effort or a cautious option.
- **9:** Clear recommendation with why; non-obvious findings surfaced (things only testing revealed);
  options include a low-risk path; concrete next actions and risks with fixes; says what would change the
  recommendation or what is still unknown.

### 4. Visual explanation

Visuals carry meaning: the reader learns from the picture, not only the text.

- **3:** Decoration, boxes-and-arrows with no information, or text pasted into panels.
- **6:** Useful visuals but mostly tables/lists; graphics don't evolve with the story or aren't to scale.
- **9:** Concrete, to-scale visuals (timings, counts, real code, real files); the story graphic evolves
  step by step; labels sit on the graphic; status uses the kit's glyph + colour; real code where it makes a
  claim tangible.

### 5. Concision and no repetition

Says each thing once, briefly, with details on demand.

- **3:** Walls of text; the same number or sentence restated in most steps; chapters that repeat each other.
- **6:** Mostly tight, but some long steps, padded chapters or a key fact restated 5+ times without new
  context.
- **9:** Steps are 1–2 short sentences; each fact has one home; details sit in toggles that name their
  contents; chapters that don't apply are skipped. Roughly 1,000–1,800 visible words for a topic like the
  baseline's.

### 6. Structure and flow

The page reads in a sensible order and is easy to navigate.

- **3:** Chapters in arbitrary order, missing headings or chapter list, story with no arc.
- **6:** Correct chapter order and chapter list, but the story is a tour of facts or chapters overlap.
- **9:** Overview → story (situation → problem → change → result → consequences) → details → decision;
  takeaway headline per chapter; chapter list with useful sub-entries; jargon briefly explained on first use.

### 7. Layout and rendering robustness

Works on desktop and phone, dark and light.

- **3:** Overflow, cut-off code/panels, unreadable text, console errors, or a broken theme.
- **6:** Works, but with visible flaws: tiny text in scaled SVGs on phone, big empty gaps beside panels,
  graphic far from its steps on phone, long code lines needing sideways scroll.
- **9:** `report.json` clean (no overflow, no cut-off sticky panels, no errors); every label legible at
  390 px; panels level with their first text box; dark and light equally finished.

### 8. Kit and skill contract

Follows `explain-visually`, the `explain-with-*` skills and `FRAGMENT-CONTRACT.md`.

- **3:** Custom themes or fonts, literal colours, bare "More" toggles, dimmed text, page not built with the
  assembler.
- **6:** Assembled with the kit, but several skill rules broken (e.g. graphic not pinned on phone, story
  appends a details block, IntersectionObserver instead of `EV.steps`, step count out of range).
- **9:** Kit used as is; overview has exactly the allowed parts; step counts in range; panels right and
  centred; first state belongs to step 1 and reverse scroll restores states; toggles name their contents.

## Hard failures

Any of these is a regression regardless of the scores. List each one found.

- The page doesn't render, `assemble.py` would reject it, or the console shows errors that break content.
- Fabricated numbers, sources, commands or results, or a claim that contradicts the run's own evidence.
- No overview, or a headline that doesn't answer the question.
- No recommendation when the user has a decision to make (as in the baseline prompt).
- Horizontal page overflow or content cut off (text, code, panels) at 1440 px or 390 px, in dark or light.
- Text meant to be read is unreadable: invisible in one theme, faded, or below ~9 px at its rendered size.
- The project's working tree was modified when the task was only to explore (check the transcript).
- Not published, or published as several linked pages.

## Baseline calibration (Opus, about 11 min)

| #   | Criterion           | Score | Why                                                                                    |
| --- | ------------------- | ----- | -------------------------------------------------------------------------------------- |
| 1   | Answers the question | 9    | Headline gives answer + trade-off + "3–5×"; to-scale hero bars; one Decide callout.    |
| 2   | Grounding           | 9     | Ran all three tools in a worktree; method, versions, sources; warm-cache caveat shown. |
| 3   | Insight / decision  | 8     | Found the crashing rule, ignored disables, unenforced Prettier; option C; no effort.   |
| 4   | Visual explanation  | 7     | Hero is excellent; story graphic is a lit-up table, no code shown.                     |
| 5   | Concision           | 8     | ~1,300 words, short steps; some numbers restated across chapters (202 × 8).            |
| 6   | Structure and flow  | 7     | Good chapter choice; story is a tool tour without an arc; jargon unexplained.          |
| 7   | Robustness          | 7     | report.json clean; hero labels ~5 px on phone; empty gaps beside tall panels.          |
| 8   | Contract            | 8     | Kit used correctly; story graphic not pinned on phone, story order not followed.       |
|     | **Total**           | **63/80** | No hard failures.                                                                  |

For contrast, the Qwen page (4 h 25 min) would score roughly 7 / 5 / 7 / 6 / 3 / 6 / 3 / 6 = 43, with hard
failures for overclaiming ("every rule carries over"), phone overflow and cut-off code.

## Taste and overall quality

Verifiers are encouraged to judge beyond this rubric: would you be happy to send this page to the user?
Does it feel considered, clear and pleasant, or mechanical? Note such judgements in a separate
**Taste notes** section, with concrete examples, and don't fold them into the criterion scores.

## Report format

```
Page: <path>   Model/run: <…>   Time: <…>
Scores: 1=_ 2=_ 3=_ 4=_ 5=_ 6=_ 7=_ 8=_  Total=_/80  (baseline 63)
Hard failures: none | <list>
Per criterion: one line each, citing an example from the page
Taste notes: <free-form>
Biggest single improvement: <one line>
```
