# Convergence: five candidates, one scorer, one recommendation

All candidates were scored with `tools/score.py` (rubric in `../scoring.md`): deterministic checks + a blind Opus
judge for quality, log-linear speed from `result.json`, page economy. Sonnet stands in for Qwen; Haiku is the
weaker proxy. Runs are in `runs/<label>/`; the full table is `final-table.md`.

## Results (facts mode; Sonnet = mean of 2 runs, baseline = 4, Haiku = 1)

| candidate | branch | overall | quality | judge | output tok | wall | turns | words / ch. | Haiku overall / quality / tok |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| unmodified skills | `explain-visually-benchmark` | 68.4 | 69.2 | 65.9 | 27.8k | 183 s | 17 | 1,550 / 5 | 57.3 / 58.7 / 37.7k |
| A (phase 1, Opus) | `ev-opt/a-opus` | 85.8 | 82.8 | 73.5 | 11.3k | 79 s | 13 | 950 / 2 | 80.6 / 80.4 / 25.0k |
| B (phase 1, Fable) | `ev-opt/b-fable` | 79.2 | 81.2 | 75.1 | 24.5k | 234 s | 13.5 | 1,140 / 3 | – |
| **C (phase 3, Opus, from A)** | `ev-opt/c-opus` | **86.7** | **84.9** | **76.8** | 11.9k | 91 s | 13.5 | 1,159 / 2 | 81.8 / **85.4** / 32.7k |
| D (phase 3, Opus, from B) | `ev-opt/d-opus` | 86.1 | 82.3 | 75.5 | **10.2k** | 86 s | 15 | 1,420 / 3 | 81.7 / 82.3 / **23.1k** |
| E (phase 3, Fable, synthesis) | `ev-opt/e-fable` | 85.0 | 84.8 | 76.6 | 16.2k | 113 s | 12.5 | 1,084 / 2 | 80.5 / 82.6 / 30.3k |

Corpus calibration on the same scorer: baseline-opus 66.5, opus-1 54.3, opus-2 50.0, qwen 34.8.

Noise: the judge varies by ±2 quality points on the same page and runs vary more, so A, C, D and E are tied on
overall; differences under ~3 are noise. B's first score (76.5) rose to 79.2 after a scorer fix: its decision
options were hidden with CSS `visibility`, which the judge's page text skipped (D found this).

## Recommendation: C (`ev-opt/c-opus`)

- **Highest quality on both proxies** (84.9 Sonnet, 85.4 Haiku) at A's token level (11.9k, −57 % vs the
  unmodified skills; about 13 instead of 31 minutes of decode at 15 tok/s). Every C run scored 100 on the
  deterministic checks: all facts present, no layout problems, one `check.py` call.
- It is A's architecture (kit-driven story, JSON decision chapter, `check.py` with a stopping rule, no brief, no
  subagents, never read kit internals) plus the fixes the judge asked for: exact-claim wording rules in the
  headline, jargon glossed on first use, one real snippet inside the decision chapter, page-mode-only contract.
- D is the runner-up: fewest output tokens (10.2k Sonnet, 23.1k Haiku), smallest read-in (contract 5.8 KB), a
  generated code chapter (`walkthrough.py`) and generator validation that refuses incomplete decision JSON. Its
  quality is 2.6 below C, within noise. If GX10 context pressure turns out to dominate, D's contract trim and
  validation are the pieces to carry over into C.
- E matches C's quality but costs 4k more tokens; its hard limits in `preview.py` (item count and length, which
  killed the one fix loop weak models fell into) are worth merging into C.

## What all winners share (vs the unmodified skills)

1. Phone pinning and step spacing are kit components (`ev-side--pin`); fragments contain no layout CSS.
2. The story is markup only: the kit drives `data-on` / `data-hl` / `data-say` from the step number.
3. The decision chapter is JSON rendered by `preview.py` (rows Keeps / Loses / Fix first / Risks / Effort, plus
   "what would change this", method and sources).
4. `check.py` with a stopping rule replaces screenshot study and hand-written Playwright scripts.
5. Default plan: Overview + Story + Decision; fragility, dependencies and complexity become option rows.
6. Facts ledger (`facts.md` as you go), research budget, ≤ 15-line plan instead of a brief, no subagents.
7. Never read `kit.css` / `kit.js`; the contract is the API, trimmed to page mode.

## Known weakness and next steps

- The story graphic is the weakest judge item for every candidate (6.5–8): a chart of bars filling in, and at
  rest C shows empty tracks. A data-driven story generator (JSON → SVG, like `preview.py`) is the next lever.
- Haiku's extra tokens are mostly its own thinking (C: 24k of 33k); the page work is lean. The real test is a
  full-mode run on the GX10 with Qwen, which also exercises the research budget and facts ledger that facts mode
  cannot.
- Merge into C: E's generator limits, D's required-field validation and contract trim.
