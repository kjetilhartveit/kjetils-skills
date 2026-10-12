# Optimisation round: state at pause

Paused mid phase 3 to save tokens. Nothing is pushed; nothing touched `main`.

## Branches and worktrees

| Branch | Worktree | Role | State |
| --- | --- | --- | --- |
| `explain-visually-optimize` | `C:\git\kjetils-skills` | orchestrator: harness + converged scorer | committed |
| `ev-opt/a-opus` | `C:\git\kjetils-skills-wt\opt-a-opus` | phase-1 A (Opus) | done, report `reports/a-opus.md` |
| `ev-opt/b-fable` | `C:\git\kjetils-skills-wt\opt-b-fable` | phase-1 B (Fable) | done, report `reports/b-fable.md` |
| `ev-opt/c-opus` | `…\opt-c-opus` (from A) | phase-3 C: lift A's quality | stopped early; uncommitted kit edits, no runs |
| `ev-opt/d-opus` | `…\opt-d-opus` (from B) | phase-3 D: cut B's tokens | stopped early; uncommitted kit edits + `walkthrough.py`, no runs |
| `ev-opt/e-fable` | `…\opt-e-fable` (from original) | phase-3 E: best of A + B, Haiku-robust | stopped while reading; no changes |

Test project worktree: `C:\git\fantasy-snooker-evbench` (f0e33eb0). Local-only `inputs/` and `runs/` are copied
into every worktree.

## Scores so far (converged scorer, `scoring.md`; Sonnet, facts mode; runs in `C:\git\kjetils-skills\docs\explain-visually-loop\runs\`)

| label | overall | quality | judge | speed | output tok | wall | turns | words / chapters |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline` (unmodified, 4 runs) | 68.4 | 69.2 | 65.9 | 61.0 | 27.8k | 183 s | 17 | 1,550 / 4–5 |
| `a-v3` (A final, 2 runs) | 85.8 | 82.8 | 73.5 | 88.1 | 11.3k | 79 s | 13 | 950 / 2 |
| `b-v4` (B final, 2 runs) | 76.5 | 76.5 | 69.1 | 63.8 | 24.5k | 234 s | 13.5 | 1,140 / 3 |
| `baseline-haiku` (1) | 57.3 | 58.7 | 57.1 | 53.7 | 37.7k | 176 s | 30 | 1,269 / 6 |
| `a-v3-haiku` (1) | 80.6 | 80.4 | 69.8 | 71.6 | 25.0k | 151 s | 13 | 1,039 / 2 |
| corpus: baseline-opus / opus-1 / opus-2 / qwen | 66.5 / 54.3 / 50.0 / 34.8 | | | | | | | |

Judge critique of A's page: jargon unexplained (clarity 5), small story graphic, headline "263 rules keep working"
is a soft overclaim. Of B's page: thin decision support (5–6), twice A's tokens.

## To resume

1. Re-spawn C, D, E with the briefs in the conversation (or one agent on E's synthesis brief, the cheapest
   path), `python tools/compare.py --baseline baseline` for the table.
2. Score every final candidate with `tools/score.py` from this checkout, copy run folders into `runs/<label>/`.
3. Recommend one (A's `a-v3` leads now), then build the visual side-by-side breakdown of the changes.
