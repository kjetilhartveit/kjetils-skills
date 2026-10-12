"""Run one explain-visually benchmark: a candidate skills folder, a model and the fixed prompt.

Usage:
    python run.py --skills <repo-or-worktree>/skills --model sonnet --label my-candidate [--mode facts|full]
                  [--project DIR] [--runs DIR] [--max-budget-usd 15] [--max-turns 200] [--timeout-min 60]

Starts `claude -p` in the frozen test project with the candidate skills exposed as files (the Skill tool is
disabled, because an installed skill with the same name would otherwise shadow the candidate). Writes one run
folder:

    <runs>/<label>/<timestamp>-<model>-<mode>/
        prompt.txt       the exact prompt sent
        stream.jsonl     the full stream-json transcript (tool calls, text, thinking, subagents)
        result.json      wall time, turns, cost, tokens per model, tool-call counts, estimated decode minutes
        out/index.html   the page the run produced (plus its working files)
        shots/, measures.json   from measure.py, when the page exists

`facts` mode hands the run a frozen facts file instead of letting it research, so runs only differ in how the
skills turn facts into a page. `full` mode is the real thing (web research, running tools) and is slower and
noisier; use it for a final check, not for the loop.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

LOOP_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = LOOP_DIR.parents[1]
DEFAULT_PROJECT = Path(os.environ.get("EVBENCH_PROJECT") or (REPO_DIR.parent / "fantasy-snooker-evbench"))
DEFAULT_RUNS = LOOP_DIR / "runs"
FACTS_FILE = LOOP_DIR / "inputs" / "facts-oxlint.md"
QWEN_TOKENS_PER_SECOND = 15

USER_PROMPT = (
    "We're looking to move away from eslint and prettier to oxlint and oxprettier or Biome. "
    "Can you help me explore this?\n\nExplain visually"
)

HARNESS_NOTES = """
---
Benchmark harness notes (these stand in for the usual skill loader; follow them):

- The `explain-visually` skill and its companion skills are plain files under {skills_dir}:
  one folder per skill with a SKILL.md, e.g. {skills_dir}/explain-visually/SKILL.md.
  Start by reading {skills_dir}/explain-visually/SKILL.md and follow it. Whenever a skill tells you to load,
  use or read another skill (`explainer-kit`, `explain-with-*`, ...), read {skills_dir}/<name>/SKILL.md.
  The Skill tool is disabled in this session.
- Write every working file and the final page under {out_dir}. The deliverable is {out_dir}/index.html.
  Do not publish an artifact and do not modify the repository you are running in.
{mode_notes}"""

FACTS_NOTES = """- The facts are already gathered in {facts_file}. Treat that file as the finished result of the
  fact-gathering step: do not search the web, do not install or run lint or format tools, do not measure
  anything. You may read files in the repository for real code snippets."""

FULL_NOTES = """- Gather the facts yourself as the skill describes. Do not modify the repository; measure in a scratch
  copy if you need to run anything."""


def build_prompt(mode: str, skills_dir: Path, out_dir: Path) -> str:
    mode_notes = FACTS_NOTES.format(facts_file=FACTS_FILE.as_posix()) if mode == "facts" else FULL_NOTES
    return USER_PROMPT + HARNESS_NOTES.format(
        skills_dir=skills_dir.as_posix(), out_dir=out_dir.as_posix(), mode_notes=mode_notes
    )


def claude_command(model: str, out_dir: Path, skills_dir: Path, budget: float, max_turns: int) -> list[str]:
    exe = shutil.which("claude") or "claude"
    return [
        exe, "-p",
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--dangerously-skip-permissions",
        "--disallowedTools", "Skill",
        "--no-session-persistence",
        "--max-budget-usd", str(budget),
        "--max-turns", str(max_turns),
        "--add-dir", str(out_dir), str(skills_dir), str(FACTS_FILE.parent),
    ]


def run_claude(cmd: list[str], prompt: str, cwd: Path, stream_path: Path, timeout_s: float) -> tuple[int, bool]:
    """Streams stdout to stream_path line by line so a run can be watched while it is going."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    with stream_path.open("w", encoding="utf-8") as stream:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        )
        assert proc.stdin and proc.stdout
        proc.stdin.write(prompt)
        proc.stdin.close()
        deadline = time.monotonic() + timeout_s
        timed_out = False
        for line in proc.stdout:
            stream.write(line)
            stream.flush()
            if time.monotonic() > deadline:
                timed_out = True
                proc.kill()
                break
        proc.wait()
    return proc.returncode, timed_out


def summarise_stream(stream_path: Path) -> dict:
    tool_calls: Counter[str] = Counter()
    subagent_tool_calls: Counter[str] = Counter()
    assistant_messages = 0
    text_chars = 0
    thinking_chars = 0
    result: dict = {}
    for raw in stream_path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw.startswith("{"):
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "result":
            result = event
        elif kind == "assistant":
            assistant_messages += 1
            in_subagent = bool(event.get("parent_tool_use_id"))
            for block in event.get("message", {}).get("content", []) or []:
                block_type = block.get("type")
                if block_type == "tool_use":
                    (subagent_tool_calls if in_subagent else tool_calls)[block.get("name", "?")] += 1
                elif block_type == "text":
                    text_chars += len(block.get("text", ""))
                elif block_type == "thinking":
                    thinking_chars += len(block.get("thinking", ""))
    return {
        "result": result,
        "tool_calls": dict(tool_calls),
        "subagent_tool_calls": dict(subagent_tool_calls),
        "assistant_messages": assistant_messages,
        "text_chars": text_chars,
        "thinking_chars": thinking_chars,
    }


def write_result(run_dir: Path, meta: dict, summary: dict, exit_code: int, timed_out: bool) -> dict:
    result = summary["result"]
    model_usage = result.get("modelUsage", {}) or {}
    output_tokens = sum(int(m.get("outputTokens", 0)) for m in model_usage.values())
    thinking_tokens = sum(int(m.get("thinkingTokens", 0)) for m in model_usage.values())
    input_tokens = sum(
        int(m.get("inputTokens", 0)) + int(m.get("cacheReadInputTokens", 0)) + int(m.get("cacheCreationInputTokens", 0))
        for m in model_usage.values()
    )
    data = {
        **meta,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "is_error": result.get("is_error", exit_code != 0),
        "terminal_reason": result.get("terminal_reason"),
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "duration_api_ms": result.get("duration_api_ms"),
        "total_cost_usd": result.get("total_cost_usd"),
        "output_tokens_total": output_tokens,
        "thinking_tokens_total": thinking_tokens,
        "input_tokens_total": input_tokens,
        "est_minutes_at_15_tok_s": round(output_tokens / QWEN_TOKENS_PER_SECOND / 60, 1),
        "usage": result.get("usage"),
        "model_usage": model_usage,
        "subagent_stats": result.get("subagent_stats"),
        "tool_calls": summary["tool_calls"],
        "subagent_tool_calls": summary["subagent_tool_calls"],
        "assistant_messages": summary["assistant_messages"],
        "text_chars": summary["text_chars"],
        "thinking_chars": summary["thinking_chars"],
        "final_text": (result.get("result") or "")[:4000],
        "index_html": (run_dir / "out" / "index.html").exists(),
    }
    (run_dir / "result.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skills", type=Path, default=REPO_DIR / "skills", help="candidate skills folder")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--label", required=True, help="candidate name; runs are grouped under it")
    parser.add_argument("--mode", choices=("facts", "full"), default="facts")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT, help="test project the run works in")
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--max-budget-usd", type=float, default=15.0)
    parser.add_argument("--max-turns", type=int, default=200)
    parser.add_argument("--timeout-min", type=float, default=60)
    parser.add_argument("--no-measure", action="store_true", help="skip screenshots and page measures")
    args = parser.parse_args()

    skills_dir = args.skills.resolve()
    project = args.project.resolve()
    if not (skills_dir / "explain-visually" / "SKILL.md").exists():
        sys.exit(f"no explain-visually/SKILL.md under {skills_dir}")
    if not project.is_dir():
        sys.exit(f"test project not found: {project} (set EVBENCH_PROJECT or --project)")
    if args.mode == "facts" and not FACTS_FILE.exists():
        sys.exit(f"facts file missing: {FACTS_FILE}")

    started = datetime.now()
    run_dir = args.runs / args.label / f"{started:%Y%m%d-%H%M%S}-{args.model}-{args.mode}"
    out_dir = run_dir / "out"
    out_dir.mkdir(parents=True)
    prompt = build_prompt(args.mode, skills_dir, out_dir)
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    cmd = claude_command(args.model, out_dir, skills_dir, args.max_budget_usd, args.max_turns)
    print(f"run {run_dir}\n  model={args.model} mode={args.mode} skills={skills_dir}\n  cwd={project}")

    wall_start = time.monotonic()
    exit_code, timed_out = run_claude(cmd, prompt, project, run_dir / "stream.jsonl", args.timeout_min * 60)
    wall_s = round(time.monotonic() - wall_start)

    meta = {
        "label": args.label, "model": args.model, "mode": args.mode,
        "skills_dir": skills_dir.as_posix(), "project": project.as_posix(),
        "started": started.isoformat(timespec="seconds"), "wall_s": wall_s,
        "max_budget_usd": args.max_budget_usd, "max_turns": args.max_turns,
    }
    data = write_result(run_dir, meta, summarise_stream(run_dir / "stream.jsonl"), exit_code, timed_out)
    print(
        f"done in {wall_s}s: turns={data['num_turns']} cost=${data['total_cost_usd']} "
        f"output_tokens={data['output_tokens_total']} (~{data['est_minutes_at_15_tok_s']} min at 15 tok/s) "
        f"index.html={'yes' if data['index_html'] else 'NO'} timed_out={timed_out}"
    )

    if data["index_html"] and not args.no_measure:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from measure import measure_run

        measure_run(run_dir)
    return 0 if data["index_html"] else 1


if __name__ == "__main__":
    sys.exit(main())
