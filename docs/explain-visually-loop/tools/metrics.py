"""Token metrics for one Claude Code session, including its subagents.

Usage: python metrics.py <session-id> [wall-seconds]

Finds ~/.claude/projects/*/<session-id>.jsonl and <session-id>/subagents/*.jsonl and sums usage per agent.
Output tokens include thinking, so they are the proxy for time on a slow local model:
est_minutes_at_15tps = total output tokens / 15 / 60 (ignores prefill and parallelism).
"""

from datetime import datetime
import glob
import json
import os
import sys
from pathlib import Path

# The harness's follow-up prompt for the reflection; everything from it on is not part of the run.
REFLECTION_MARKER = "The benchmark run is over"


def run_lines(path: str):
    """Transcript lines up to (not including) the harness's reflection prompt."""
    for line in open(path, encoding="utf-8"):
        if REFLECTION_MARKER in line and '"type":"user"' in line.replace(" ", ""):
            return
        yield line


def usage_of(path: str) -> dict:
    """Sums usage once per API message. The transcript has one line per content block (thinking, text, each
    tool call), and every line repeats the message's usage, so summing lines double- or triple-counts."""
    per_message: dict[str, dict] = {}
    tool_calls = 0
    models = set()
    for line in run_lines(path):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = d.get("message")
        if d.get("type") != "assistant" or not isinstance(msg, dict):
            continue
        key = msg.get("id") or d.get("requestId") or d.get("uuid")
        per_message[key] = msg.get("usage") or {}  # the last line of a message carries its final usage
        tool_calls += sum(1 for c in msg.get("content") or [] if isinstance(c, dict) and c.get("type") == "tool_use")
        if msg.get("model"):
            models.add(msg["model"])
    usages = per_message.values()
    return {
        "turns": len(per_message),
        "output": sum(u.get("output_tokens", 0) for u in usages),
        "input": sum(u.get("input_tokens", 0) for u in usages),
        "cache_read": sum(u.get("cache_read_input_tokens", 0) for u in usages),
        "cache_create": sum(u.get("cache_creation_input_tokens", 0) for u in usages),
        "tool_calls": tool_calls,
        "models": sorted(models),
    }


def active_seconds(path: str) -> int | None:
    """Seconds from the first to the last timestamped entry: the run's working time, unlike wall time,
    which can include a process idling after the work is done."""
    stamps = []
    for line in run_lines(path):
        try:
            ts = json.loads(line).get("timestamp")
        except json.JSONDecodeError:
            continue
        if ts:
            stamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
    return int((max(stamps) - min(stamps)).total_seconds()) if stamps else None


def main(session_id: str, wall: str | None) -> None:
    root = Path.home() / ".claude" / "projects"
    mains = glob.glob(str(root / "*" / f"{session_id}.jsonl"))
    if not mains:
        print(json.dumps({"error": f"no transcript for {session_id}"}))
        return
    main_path = mains[0]
    subs = sorted(glob.glob(os.path.join(main_path[:-6], "subagents", "*.jsonl")))
    agents = {"main": usage_of(main_path)} | {Path(s).stem: usage_of(s) for s in subs}
    total_out = sum(a["output"] for a in agents.values())
    result = {
        "session_id": session_id,
        "transcript": main_path,
        "wall_seconds": int(wall) if wall else None,
        "active_seconds": active_seconds(main_path),
        "subagents": len(subs),
        "total_output_tokens": total_out,
        "total_turns": sum(a["turns"] for a in agents.values()),
        "total_tool_calls": sum(a["tool_calls"] for a in agents.values()),
        "total_uncached_input": sum(a["input"] + a["cache_create"] for a in agents.values()),
        "total_cache_read": sum(a["cache_read"] for a in agents.values()),
        "est_minutes_at_15tps": round(total_out / 15 / 60, 1),
        "agents": agents,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
