# Explain-visually optimisation loop

Goal: make `explain-visually` (and the `explain-with-*` / `explainer-kit` skills it uses) produce explainers with
fewer tokens and less time on weaker, slower models (Sonnet 5.5 as the proxy, later Qwen 3.8 27B on the GX10 at
~15 tokens/s), **without lowering quality**. A quality drop is a regression.

## Files

| File                          | What it is                                                                            |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| `01-baseline-analysis.md`     | What the Opus baseline does well and badly; what to strive for                       |
| `02-qwen-session-analysis.md` | Where the Qwen run's 4 h 25 min and tokens went; ranked potential gains               |
| `rubric.md`                   | How verifiers score a page (8 criteria, 1–10, hard failures, baseline calibration 63) |
| `problems.md`                 | Known problems from earlier runs and their analyses, with what was tried              |
| `tools/`                      | Harness scripts and the verifier prompt (below)                                       |
| `inputs/`, `iterations/`      | Local only (git-ignored): baseline/Qwen inputs, reference facts, every run's output   |

A first attempt (small experiments on chunks of the page, with whole-page checkpoints) improved the research but
not the pages overall. Its results, runs and skill patches are archived outside the repo in
`kjetils-skills archive/explain-visually-loop-2026-10/` (OneDrive); its lessons are in `problems.md`.

## Preparation (do this before every session of runs)

- **Free memory.** Each run makes its own fantasy-snooker worktree, runs `pnpm install`, and the agent runs ESLint
  (type-aware), oxlint, Biome and Playwright, next to a Claude process and its subagents. Three parallel runs, and
  later even one run with heavy apps open, pushed a 32 GB machine critically low; Claude Code then kills the
  background job (the run is lost, nothing to debug). Close heavy apps (Discord, extra Chrome/Cursor windows)
  first and keep runs **serial**. Optionally start Claude Code with
  `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` so background jobs aren't killed (it doesn't free memory).
- Python Playwright with Chromium installed (`pip install playwright && playwright install chromium`).
- fantasy-snooker cloned at `C:\git\fantasy-snooker` with the pinned commit available (see `run_explainer.sh`).
- Work on the `explain-visually-benchmark` branch of this repo (or a branch from it); the runs read the skills from the working tree.

## How a run works (`tools/run_explainer.sh <iteration> <run> [model]`)

1. Makes a throwaway worktree of fantasy-snooker at the pinned commit under `C:\git\evloop-runs\` and installs
   dependencies.
2. Copies the installed user skills plus this branch's candidate `explain*` / `explainer-kit` skills into a folder
   **outside** the worktree, loaded with `--add-dir`. Runs use `--setting-sources project,local`, because
   otherwise the installed copies of the explain skills win over the candidates.
3. Runs `claude -p` headless with the baseline prompt and a short harness note: unattended, no Artifact tool
   (headless sessions don't have one), so write the page to `index.html`; Playwright is available; don't change
   tracked files. `ScheduleWakeup` is disallowed (an uncancelled wakeup kept a run alive 40 extra minutes).
4. Records `metrics.json` from the transcripts (output tokens incl. thinking, turns, tool calls, subagents, active
   time, minutes at 15 tok/s), screenshots with `tools/shoot.py`, then asks the same session for a short
   `reflection.md` (after measuring, so it doesn't count).

`tools/run_iteration.sh <iteration> [model] [runs]` runs several whole-page runs one after another (default: Sonnet, 2).

`tools/run_chunk.sh <experiment> <variant> <sample> [model]` runs one part of the job with fixed inputs, e.g. one
chapter built from `inputs/facts-oxlint.md`, with an optional skill overlay per variant (see the script's header).

Verify a run with an Opus agent given `tools/verifier-prompt.md` (with `{RUN_DIR}` filled in) and `rubric.md`.

## Lessons from the first attempt

- Runs vary by several rubric points; one run per model is a smoke test, not a result.
- A change that wins in isolation can still be undone in the whole flow (e.g. the coordinator overriding a chapter
  skill), and better facts don't make a better page by themselves: they made pages longer.
- Make the scoring identical between runs you compare (same verifier prompt and checks).
