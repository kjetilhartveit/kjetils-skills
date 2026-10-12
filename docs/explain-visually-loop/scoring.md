# Scoring a run

`tools/score.py` turns one run (or any explainer page) into one comparable number plus a breakdown, written to
`score.json` next to `measures.json`.

```bash
python tools/score.py runs/<label>/<run>                              # a run: quality + speed + economy
python tools/score.py inputs/corpus/qwen.html --out runs/corpus/qwen  # a bare page: quality + economy
python tools/score.py runs/<label>/<run> --no-judge                   # deterministic parts only (free, ~1 min)
```

It re-uses `measures.json` and `shots/` when they exist (`--remeasure` forces `measure.py`). The judge costs about
$0.35–0.45 per page with Opus and takes 2–4 minutes; runs can be scored in parallel.

## Formula

```
quality  Q = 0.35 × checks + 0.65 × judge                       0–100
economy  S = mean(words band, page bytes, chapter count)        0–100
speed    E = weighted output tokens, wall time, turns, cost, context   0–100 (runs only)

overall (run)  = 0.60 Q + 0.25 E × min(1, Q / 80) + 0.15 S
overall (page) = (0.60 Q + 0.15 S) / 0.75
```

Quality dominates, and speed only counts in full once quality reaches 80: a fast run that produces a weak page
can't buy its way up. Economy rewards pages in the 1,000–1,800-word band and penalises both bloat and thin pages.

## Quality: deterministic checks (100 points, 35 % of Q)

| Part | Points | What |
| --- | --- | --- |
| Facts | 40 | 13 key facts found in the page text (regex alternatives in `KEY_FACTS`, plus source links to oxc.rs / biomejs.dev), minus 10 per overclaim (`OVERCLAIMS`: "every rule carries over", "every plugin family carries over", "drop-in replacement", "no rules lost"), at most −20 |
| Layout | 30 | From `shots/report.json`: −5 / −3 horizontal overflow (phone / desktop), −2.5 per view with sticky panels cut off or console errors, up to −2.5 for code that scrolls sideways, up to −4 per phone view for SVG labels under 9 px, up to −4 per view for scroll steps whose panel is out of view or covers the step |
| Structure | 30 | ≤ 4 chapters (8; 5 chapters 4), story with 4–9 steps (5), a decision chapter (5), ≥ 900 words (4, scaled down to 500), no literal colours in fragment CSS (4), toggles that name their contents (4) |

`shoot.py` scrolls every `ev-step` to the reading line on desktop and phone to find panels out of view, and writes
the story screenshots (`story-desktop-step*.png`, `story-phone-step*.png`) and `page.txt` (all toggles opened) for
the judge.

## Quality: the blind judge (100 points, 65 % of Q)

`claude -p --model opus` with only the Read tool, in a fresh temporary folder that holds `facts.md` (the facts
file), `page.txt` and the screenshots under neutral names. It never sees the run label, path, transcript or
skills. It returns 0–10 per criterion (JSON schema) plus a list of factual errors:

| Criterion | Weight | Asks |
| --- | --- | --- |
| headline | 15 | The overview answers the question (which tool, the trade-off) with key numbers before scrolling |
| accuracy | 20 | Substance agrees with the facts: no overclaims, contradictions or invented findings |
| numbers | 5 | Numbers match the facts, are consistent, nothing invented |
| story | 15 | An arc, and one graphic that evolves step by step, concrete and to scale |
| decision | 20 | 2–3 options incl. a cautious one, a recommendation, effort, risks with fixes, what would change it |
| concision | 15 | Answer fast, details findable, no padding or repetition; thin pages are penalised too |
| visual | 10 | Clean and legible on desktop and phone, both themes, nothing cut off or empty |

## Speed (runs only)

Each value maps linearly to 100 at "good" and 0 at "bad", clamped:

| Value (`result.json`) | Weight | 100 at | 0 at |
| --- | --- | --- | --- |
| `output_tokens_total` (≈ GX10 minutes) | 0.50 | 10k | 60k |
| `wall_s` | 0.15 | 120 s | 1,200 s |
| `num_turns` | 0.10 | 10 | 80 |
| `total_cost_usd` | 0.15 | $0.30 | $3.00 |
| `input_tokens_total` (context pressure) | 0.10 | 300k | 3M |

## Economy

Words: 100 inside 1,000–1,800, down to 0 at 5,000 (bloat) or at 400 (thin). Bytes: 100 up to 130 KB, 0 at 300 KB.
Chapters: 3–4 → 100, 2 → 80, 5 → 70, 6 → 40, more → 10.

## Calibration (corpus, judge = Opus)

| Page | Overall | Quality | Checks (facts / layout / structure) | Judge | Economy |
| --- | --- | --- | --- | --- | --- |
| baseline-opus | **68.5** | 60.7 | 33.8 / 14.0 / 28 | 52.5 | 100 |
| opus-1 | 57.3 | 65.1 | 33.8 / 15.0 / 22 | 62.0 | 26.3 |
| opus-2 | 49.7 | 55.6 | 30.8 / 5.8 / 22 | 54.0 | 26.0 |
| qwen | 32.9 | 33.8 | 0 / 2.0 / 22 | 39.0 | 29.3 |

baseline-opus is clearly first overall and qwen clearly last. On quality alone opus-1 edges baseline-opus: opus-1
was made from the same measurement run as `facts-oxlint.md`, while baseline-opus measured in its own session
(29.4 s, 185 files, 202 comments), so the judge marks its numbers down (numbers 1/10, accuracy 4/10). That is a
property of the corpus, not of the skills; in `facts` mode every candidate gets the same facts file. The phone
checks also catch the baseline's two known flaws (hero labels unreadable at 390 px, story panel never visible with
its step on a phone).

## Caveats

- The judge varies by roughly ±3 points of judge score between calls on the same page; compare candidates on
  2+ runs, and treat overall differences under ~3 as noise.
- Facts regexes are specific to the oxlint/Biome task; a new task needs new `KEY_FACTS` and `OVERCLAIMS`.
