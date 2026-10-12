# explain-visually loop

Benchmark harness for making the `explain-visually` skill (and the `explain-with-*` and `explainer-kit` skills it
uses) faster and cheaper on weaker, slower models without losing quality. The target is Qwen 3.8 27B FP8 on the
GX10 at ~15 tokens/s; Claude Sonnet (or Haiku, weaker) stands in for it during the loop.

Start with `01-baseline-analysis.md` (what a good page looks like, what to strive for) and
`02-qwen-session-analysis.md` (where the slow model spent 4 h 25 min, and the ranked list of likely gains).

## Fixed task

Every run gets the same prompt, in the same project (`fantasy-snooker` frozen at `f0e33eb0`):

```
We're looking to move away from eslint and prettier to oxlint and oxprettier or Biome. Can you help me explore this?

Explain visually
```

`inputs/facts-oxlint.md` holds the facts that question needs, gathered and measured once. In `facts` mode a run
gets that file instead of researching, so runs only differ in how the skills turn facts into a page. `full` mode
is the real thing (research, running the tools) and is only for a final check.

## Files

| Path | What |
| --- | --- |
| `tools/run.py` | Runs one candidate: `claude -p` in the test project with the candidate skills exposed as files. Writes the transcript, `result.json` (wall time, turns, cost, tokens per model, tool calls) and the page. |
| `tools/measure.py` | Deterministic page measures (bytes, words, chapters, steps, code blocks, chips, toggles, links) plus the layout checks and screenshots from `shoot.py`. Works on a run folder or any `.html`. |
| `tools/shoot.py` | Playwright screenshots (desktop and phone, dark and light, the story at its first, middle and last step), `page.txt` (rendered text with every toggle and hidden panel opened) and `report.json` with overflow, cut-off panels, unreadable SVG labels, steps whose panel is out of view, and console errors. |
| `tools/score.py` | One comparable score per run or page: deterministic checks + a blind Opus judge for quality, log-linear speed, page economy. Rubric in `scoring.md`. |
| `tools/compare.py` | Markdown table of every scored run, with a quality gate against a baseline label. |
| `tools/analyse_session.py` | Token and time breakdown of an OpenCode transcript export (used for `02-…`). |
| `inputs/` (local only) | Facts file, the baseline and Qwen transcripts, and `corpus/` with four finished pages: `baseline-opus.html` (the good one), `qwen.html` (slow and bloated), `opus-1.html` / `opus-2.html` (Opus with the current skills: 7 chapters, ~5,000 words, i.e. the current skills over-produce even on a strong model). |
| `runs/` (local only) | One folder per run: `<label>/<timestamp>-<model>-<mode>/`. |

## Running

Prerequisites: Python 3.10+, `playwright` with Chromium (`pip install playwright && playwright install chromium`),
the `claude` CLI, and a worktree of the test project at `../fantasy-snooker-evbench` (or `EVBENCH_PROJECT`):

```bash
git -C ../fantasy-snooker worktree add --detach ../fantasy-snooker-evbench f0e33eb0
```

```bash
cd docs/explain-visually-loop
python tools/run.py --skills ../../skills --model sonnet --label baseline          # the unmodified skills
python tools/run.py --skills /path/to/worktree/skills --model sonnet --label my-candidate
python tools/score.py runs/my-candidate/<run>                                        # score it (judge: Opus, ~$0.4)
python tools/score.py inputs/corpus/baseline-opus.html                               # score a corpus page
python tools/compare.py --baseline baseline                                          # table of every scored run
```

`result.json` fields that matter: `wall_s`, `num_turns`, `total_cost_usd`, `output_tokens_total` (what the slow
model has to generate: the best proxy for GX10 minutes, also given as `est_minutes_at_15_tok_s`),
`thinking_tokens_total`, `input_tokens_total` (context pressure), `tool_calls`, `subagent_stats`, `index_html`.

Why skills are exposed as files: an installed skill with the same name (`~/.claude/skills/explain-visually`)
shadows a project-level or `--add-dir` skill, so the run disables the Skill tool and the prompt points at the
candidate's `SKILL.md` files instead. That is also how OpenCode and the Qwen run consume skills.

## Rules for optimisation runs

- Work on a branch in your own worktree; never on `main`. Commit with conventional commits as you go; don't push.
- Never modify the test project (`fantasy-snooker`, including the `-evbench` worktree).
- Measure the unmodified skills with the same harness, model and mode before claiming an improvement, and
  run each candidate at least twice: single runs vary a lot.
- Quality is not negotiable: a faster skill that produces a worse explainer (see "What we should strive for" in
  `01-baseline-analysis.md`) is not an improvement. Score quality blind, i.e. without knowing which candidate made
  the page, and calibrate the scoring on the corpus (`baseline-opus` must score well, `qwen` poorly).
- Prefer deterministic tools and kit components over instructions that make the model think more.
