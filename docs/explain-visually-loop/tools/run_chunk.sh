#!/usr/bin/env bash
# One run of a chunk experiment: a single chapter built from the frozen facts, no repo or worktree needed.
#
# Usage: run_chunk.sh <experiment> <variant> <sample> [model]
#
# - experiments/<experiment>/prompt.md is the task; {WORK} in it is replaced by the run folder.
# - Skills: the user's installed skills, then this branch's explain*/explainer-kit skills, then the variant's
#   overlay (experiments/<experiment>/<variant>/skills/, if any) on top. Loaded with --add-dir and
#   --setting-sources project,local, as in run_explainer.sh.
# - The run folder gets facts.md (inputs/facts-oxlint.md), or, if experiments/<experiment>/needs-repo exists, a
#   throwaway worktree of fantasy-snooker at the pinned commit in {WORK}/repo (the run's working folder) instead.
# - Results go to experiments/<experiment>/runs/<variant>-<sample>/.
set -euo pipefail

EXP="$1"; VARIANT="$2"; SAMPLE="$3"; MODEL="${4:-sonnet}"
SKILLS_REPO="/c/git/kjetils-skills"
LOOP_DIR="$SKILLS_REPO/docs/explain-visually-loop"
EXP_DIR="$LOOP_DIR/experiments/$EXP"
WORK="/c/git/evloop-runs/$EXP/$VARIANT-$SAMPLE"
OUT="$EXP_DIR/runs/$VARIANT-$SAMPLE"

rm -rf "$WORK" "$OUT"; mkdir -p "$WORK/out" "$OUT"
RUN_CWD="$WORK"
if [ -f "$EXP_DIR/needs-repo" ]; then
  git -C /c/git/fantasy-snooker worktree prune
  git -C /c/git/fantasy-snooker worktree add --detach "$WORK/repo" f0e33eb0d5bd2653ad5c808ccd5528ffb96faa23 >/dev/null
  cp /c/git/fantasy-snooker/.env* "$WORK/repo/" 2>/dev/null || true
  (cd "$WORK/repo" && pnpm install --frozen-lockfile --prefer-offline >"$WORK/pnpm-install.log" 2>&1)
  RUN_CWD="$WORK/repo"
else
  cp "$LOOP_DIR/inputs/facts-oxlint.md" "$WORK/facts.md"
fi

SKILLS_DIR="$WORK/skills/.claude/skills"
mkdir -p "$SKILLS_DIR"
cp -r "$HOME"/.claude/skills/* "$SKILLS_DIR/"
for d in "$SKILLS_REPO"/skills/explain*/ "$SKILLS_REPO"/skills/explainer-kit/; do
  rm -rf "$SKILLS_DIR/$(basename "$d")"
  cp -r "$d" "$SKILLS_DIR/"
done
[ -d "$EXP_DIR/$VARIANT/skills" ] && cp -r "$EXP_DIR/$VARIANT/skills/." "$SKILLS_DIR/"
git -C "$SKILLS_REPO" rev-parse HEAD >"$OUT/skills-commit.txt"

PROMPT="$(sed "s#{WORK}#$WORK#g" "$EXP_DIR/prompt.md")"
HARNESS_NOTE="Unattended benchmark run: nobody will answer questions, so make reasonable choices yourself and finish the task.
Python Playwright with Chromium is installed."

cd "$RUN_CWD"
START=$(date +%s)
timeout 1500 claude -p --model "$MODEL" --permission-mode bypassPermissions --setting-sources project,local \
  --disallowed-tools ScheduleWakeup --add-dir "$WORK/skills" --output-format json \
  --append-system-prompt "$HARNESS_NOTE" -- "$PROMPT" </dev/null >"$OUT/result.json" 2>"$OUT/stderr.log" || true
END=$(date +%s)

SID=$(python -c "import json,sys; print(json.load(open(sys.argv[1]))['session_id'])" "$OUT/result.json" 2>/dev/null || echo "")
echo "$SID" >"$OUT/session-id.txt"
python "$LOOP_DIR/tools/metrics.py" "$SID" "$((END - START))" >"$OUT/metrics.json" || true
cp -r "$WORK"/out/* "$OUT/" 2>/dev/null || true
echo "done $EXP $VARIANT-$SAMPLE: $((END - START))s"
