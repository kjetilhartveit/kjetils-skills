#!/usr/bin/env bash
# One benchmark run of the explain-visually skill, headless on a given model.
#
# Usage: run_explainer.sh <iteration> <run> [model]   (iteration may be a label, e.g. -opus-check)
#
# - Makes a throwaway worktree of fantasy-snooker at the pinned commit (outside both repos).
# - Gives it the user's installed skills plus the candidate explain-*/explainer-kit skills from this
#   branch in a skills folder OUTSIDE the worktree, loaded with --add-dir (fantasy-snooker's
#   .claude/skills links to .agents/skills, so copies there got linted), and runs with
#   --setting-sources project,local so the installed copies of the explain skills don't shadow the
#   candidates (verified: user skills win otherwise; --add-dir skills still load with this setting).
# - ScheduleWakeup is disallowed: an uncancelled fallback wakeup kept a -p run alive for 40 extra minutes.
# - Each run is capped at 45 minutes: a hung ESLint once left a run idling for almost 3 hours.
# - Runs the baseline prompt, then measures tokens and active time from the transcripts, then asks the same
#   session for a short reflection (after measuring, so it doesn't count).
# - Copies index.html, metrics and the reflection to docs/explain-visually-loop/iterations/.
set -euo pipefail

ITER="$1"; RUN="$2"; MODEL="${3:-sonnet}"
SKILLS_REPO="/c/git/kjetils-skills"
TEST_REPO="/c/git/fantasy-snooker"
PINNED_SHA="f0e33eb0d5bd2653ad5c808ccd5528ffb96faa23"
LOOP_DIR="$SKILLS_REPO/docs/explain-visually-loop"
WORK="/c/git/evloop-runs/iter$ITER/run$RUN"
OUT="$LOOP_DIR/iterations/iter$ITER/run$RUN"
PROMPT="We're looking to move away from eslint and prettier to oxlint and oxprettier or Biome. Can you help me explore this?

Explain visually"

rm -rf "$WORK" "$OUT"; mkdir -p "$WORK" "$OUT"
git -C "$TEST_REPO" worktree prune
git -C "$TEST_REPO" worktree add --detach "$WORK/repo" "$PINNED_SHA" >/dev/null
cp -r "$TEST_REPO"/.env* "$WORK/repo/" 2>/dev/null || true
(cd "$WORK/repo" && pnpm install --frozen-lockfile --prefer-offline >"$WORK/pnpm-install.log" 2>&1)

# Installed user skills first, then the candidates from this branch on top, outside the worktree.
SKILLS_DIR="$WORK/skills/.claude/skills"
mkdir -p "$SKILLS_DIR"
for d in "$HOME"/.claude/skills/*/; do
  name="$(basename "$d")"
  [ -e "$WORK/repo/.claude/skills/$name" ] || cp -r "$d" "$SKILLS_DIR/$name"
done
for d in "$SKILLS_REPO"/skills/explain*/ "$SKILLS_REPO"/skills/explainer-kit/; do
  name="$(basename "$d")"
  rm -rf "$SKILLS_DIR/$name"
  cp -r "$d" "$SKILLS_DIR/$name"
done
git -C "$SKILLS_REPO" rev-parse HEAD >"$OUT/skills-commit.txt"
git -C "$SKILLS_REPO" diff --stat HEAD -- skills >>"$OUT/skills-commit.txt" || true

HARNESS_NOTE="Unattended benchmark run: nobody will answer questions, so make reasonable choices yourself and finish the task.
The Artifact tool isn't available here. Instead of publishing, write the final single page to $WORK/index.html (absolute path) and treat that as publishing.
Python Playwright with Chromium is installed if you want screenshots.
Don't change tracked files in this repository; throwaway worktrees or copies elsewhere are fine."

CLAUDE_ARGS=(-p --model "$MODEL" --permission-mode bypassPermissions --setting-sources project,local
  --disallowed-tools ScheduleWakeup --add-dir "$WORK/skills")

cd "$WORK/repo"
START=$(date +%s)
timeout 2700 claude "${CLAUDE_ARGS[@]}" --output-format json --append-system-prompt "$HARNESS_NOTE" -- "$PROMPT" \
  </dev/null >"$OUT/result.json" 2>"$OUT/stderr.log" || true
END=$(date +%s)
echo "$((END - START))" >"$OUT/wall-seconds.txt"

SID=$(python -c "import json,sys; print(json.load(open(sys.argv[1]))['session_id'])" "$OUT/result.json" 2>/dev/null || echo "")
echo "$SID" >"$OUT/session-id.txt"
python "$LOOP_DIR/tools/metrics.py" "$SID" "$((END - START))" >"$OUT/metrics.json" || true

[ -f "$WORK/index.html" ] && cp "$WORK/index.html" "$OUT/index.html"
if [ -f "$OUT/index.html" ]; then
  python "$LOOP_DIR/tools/shoot.py" "$OUT/index.html" "$OUT/shots" >/dev/null 2>&1 || echo "shoot failed" >>"$OUT/stderr.log"
fi

if [ -n "$SID" ]; then
  claude "${CLAUDE_ARGS[@]}" --resume "$SID" -- "The benchmark run is over; don't change the page. Write a short reflection (under 40 lines) to $OUT/reflection.md: what slowed you down or confused you in the explain-visually / explain-with-* / explainer-kit skills, steps that felt unnecessary, errors you hit and how you recovered, and concrete suggestions to make the skills faster to follow without lowering the quality of the explainer." \
    </dev/null >/dev/null 2>>"$OUT/stderr.log" || true
fi
echo "done iter$ITER run$RUN: $(cat "$OUT/wall-seconds.txt")s"
