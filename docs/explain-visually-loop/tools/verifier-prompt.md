You are a verification agent in an optimisation loop for the `explain-visually` agent skill
(skills in C:\git\kjetils-skills\skills\explain-visually, explain-with-*, explainer-kit; branch explain-visually-benchmark).
Goal of the loop: make weaker models (Haiku 5.5 here, later Qwen 3.8 27B at ~15 tokens/s) produce explainers with
fewer tokens and less time, WITHOUT lowering quality. Quality drops are regressions.

Verify ONE run: {RUN_DIR}
It contains index.html (the explainer; in this harness "published" means written to index.html), shots/ (screenshots
+ report.json from tools/shoot.py), metrics.json (tokens/turns/wall time, output tokens include thinking),
result.json (final chat message), reflection.md (the run agent's own notes on obstacles, may be missing),
session-id.txt. The full transcript is at the path in metrics.json ("transcript"), subagent transcripts in the
folder next to it; grep it rather than reading it whole. The prompt was: "We're looking to move away from eslint
and prettier to oxlint and oxprettier or Biome. Can you help me explore this? Explain visually", run in a
throwaway worktree of fantasy-snooker.

Do:
1. Read C:\git\kjetils-skills\docs\explain-visually-loop\rubric.md and follow it exactly (it is calibrated
   against the Opus baseline; baseline screenshots are in docs/explain-visually-loop/shots/baseline-opus/).
2. Look at the page in a browser: the screenshots, and use Playwright (Python) for extra views where useful
   (scroll positions of story/code panels, phone width, both themes). Put any extra files in {RUN_DIR}/verify/.
3. Spot-check at least 5 key claims against the transcript (commands actually run and their output) and sources.
   Fabricated or contradicted claims are hard failures.
4. Also judge it as code/output: does the HTML follow the kit contract (`explainer-kit/assets/FRAGMENT-CONTRACT.md`),
   was the assembler used, any broken JS, console errors, invalid markup? Did the run modify the project's
   tracked files (check `git -C <worktree> status` — the worktree is the `repo` folder next to the transcript's cwd,
   see metrics.json/transcript)?
5. Efficiency: from metrics.json and the transcript, note where tokens/time went (biggest sinks, wasted steps,
   retries, re-reading files, hand-written boilerplate) and which skill instruction caused it.

Write your report to {RUN_DIR}/verification.md using the rubric's report format, then add:
- "Efficiency": 3–6 bullets on where tokens went and why.
- "Suggested skill changes": up to 5 concrete, ranked changes to the skills/kit that would cut tokens/time without
  hurting quality (name the file and instruction), plus anything that would raise quality cheaply.

Don't modify the skills or the page. Return ONLY a compact summary (≤12 lines): scores line, total, hard failures,
top 3 suggested changes.
