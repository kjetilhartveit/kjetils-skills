# Scoring a run

`tools/score.py` turns one run (or any explainer page) into one comparable number plus a breakdown, written to
`score.json` next to `measures.json`. It merges the two phase-1 scorers (reports `a-opus` and `b-fable`): A's
rendered page text, per-step layout checks and quality gate, B's nine-item judge rubric and log-linear speed
anchors, and the union of both fact-anchor sets.

```bash
python tools/score.py runs/<label>/<run>                    # a run: quality + speed + economy
python tools/score.py inputs/corpus/qwen.html               # a bare page: quality + economy (→ runs/corpus/qwen)
python tools/score.py runs/<label>/<run> --no-judge         # deterministic parts only (free, ~1 min)
python tools/score.py runs/<label>/<run> --rejudge --judge-runs 2   # fresh judgement, averaged over 2 calls
python tools/compare.py --baseline baseline                 # markdown table of every scored run, with the quality gate
```

It re-uses `measures.json` and `shots/` when they exist (`--remeasure` forces `measure.py`) and caches the
judge's verdict in `judge.json`. One Opus judgement costs about $0.4 and takes 2–4 minutes; runs can be scored in
parallel.

## Formula

```
quality  Q = 0.35 × checks + 0.65 × judge                           0–100
speed    E = log-linear output tokens, wall time, turns, cost, context  0–100 (runs only)
economy  S = mean(words band, page bytes, chapter count)            0–100

overall (run)  = 0.60 Q + 0.25 E × min(1, Q / 75) + 0.15 S
overall (page) = (0.60 Q + 0.15 S) / 0.75
```

Quality dominates, and speed only counts in full once quality reaches 75: a fast run that produces a weak page
can't buy its way up. `compare.py --baseline LABEL` adds a **quality gate**: a candidate is an improvement only when
its mean quality is within 3 points of the baseline's (or higher) and its overall is higher.

## Quality: deterministic checks (100 points, 35 % of Q)

| Part | Points | What |
| --- | --- | --- |
| Facts | 40 | 18 anchors found in the rendered page text (regex alternatives in `KEY_FACTS`: oxfmt named, 263 rules, the 276/295 base, Biome's 163/55 %, timings in seconds, the react-x crash, type-aware/tsgolint, testing-library, local rules, eslint-disable, the oxfmt-first path, format drift, line endings, "alpha", effort per option, lost path checks, what would flip the call, plus a source link to oxc.rs/biomejs.dev), minus 5 per overclaim (`OVERCLAIMS`: "every rule carries over", "every plugin family carries over", "drop-in / no rules lost"), at most −15 |
| Layout | 30 | From `shots/report.json`: −5 / −3 horizontal overflow (phone / desktop, naming the outermost element), −2.5 per view with sticky panels cut off or console errors, up to −2.5 for code that scrolls sideways, −3 for a pinned phone panel over 60 % of the viewport, up to −4 per phone view for SVG labels under 9 px, up to −4 per view for scroll steps whose panel is out of view or covers the step |
| Structure | 30 | ≤ 4 chapters (8; 5 chapters 4), story with 4–9 steps (5), a decision chapter (5), ≥ 900 words (4, scaled down to 500), no literal colours in fragment CSS (4), toggles that name their contents (4) |

`shoot.py` scrolls every `ev-step` to the reading line on desktop and phone to find panels out of view, writes the
story screenshots (`story-desktop-step*.png`, `story-phone-step*.png`) and `page.txt` (rendered text with all
toggles opened and hidden panels shown, SVG labels listed) for the judge.

## Quality: the blind judge (100 points, 65 % of Q)

`claude -p --model opus` with only the Read tool, in a fresh temporary folder that holds `facts.md` (the facts
file), `page.txt` and the screenshots under neutral names. It never sees the run label, path, transcript or
skills, and is told not to guess the author. It returns 0–10 per criterion (JSON schema), a list of factual
errors and a two-sentence verdict:

| Criterion | Weight | Asks |
| --- | --- | --- |
| headline | 10 | The overview answers the question (which tool, the trade-off) with key numbers before scrolling |
| accuracy | 15 | Substance agrees with the facts: no overclaims, contradictions, invented findings or wrong tool names |
| evidence | 10 | Numbers come with method and conditions; sources linked; limits stated |
| story | 15 | An arc, and one concrete graphic that evolves step by step (from the story screenshots) |
| decision | 15 | 2–3 options incl. a cautious one, a recommendation, effort, risks with fixes, what would change it |
| concision | 10 | Answer fast, details findable, no padding or repetition; thin pages are penalised too |
| clarity | 10 | Jargon explained on first use; brief real code or config where it makes a claim concrete |
| phone | 8 | Legible at 390 px, nothing cut off, graphic pinned and visible with its step mid-story |
| desktop | 7 | Panels level with their first text box, no empty areas, finished in dark and light |

## Speed (runs only)

Log-linear between anchors (100 at or below `best`, 0 at or above `worst`), weighted:

| Value (`result.json`) | Weight | 100 at | 0 at | Why |
| --- | --- | --- | --- | --- |
| `output_tokens_total` | 0.45 | 8k | 100k | what the slow model has to generate: the GX10-minutes proxy (÷ 900 ≈ minutes) |
| `wall_s` | 0.20 | 60 s | 1,800 s | |
| `num_turns` | 0.10 | 6 | 120 | each turn is a prefill of the whole context |
| `total_cost_usd` | 0.10 | $0.20 | $12 | |
| `input_tokens_total` | 0.15 | 300k | 20M | context pressure (sum over turns, cache reads included) |

## Economy

Words: 100 inside 1,000–1,800, down to 0 at 5,000 (bloat) or at 400 (thin). Bytes: log-linear, 100 at ≤ 100 KB,
0 at ≥ 320 KB. Chapters: 3–4 → 100, 2 → 90, 5 → 70, 6 → 40, 1 → 40, more → 10.

## Calibration (corpus and the phase-1 final pages, judge = Opus)

See `reports/convergence.md` for the table. Required order: `baseline-opus` clearly above `opus-1`/`opus-2`, those
above `qwen`. Known corpus quirk (from both phase-1 scorers): `opus-1`/`opus-2` were made from the same
measurement run as `facts-oxlint.md`, while `baseline-opus` measured in its own session (29.4 s, 185 files, 202
comments), so the judge marks its numbers down a little. In `facts` mode every candidate gets the same facts file.

## Caveats

- The judge is stable to about ±1 point of quality on the same page (phase 1 measured 70.3 / 69.7 / 70.0). Runs
  vary far more, so compare candidates on 2+ runs and treat overall differences under ~3 as noise.
- Facts regexes and the judge prompt are specific to the oxlint/Biome task; a new task needs new `KEY_FACTS`,
  `OVERCLAIMS` and request text.
- The harness's layout checks only use kit class names both phase-1 kits share (`ev-step`, `ev-stick`, `ev-side`,
  `ev-code`), so the scorer does not change when a candidate changes the kit.
