"""Analyse an OpenCode transcript export (markdown) of an explain-visually run.

Splits the transcript into events (thinking, assistant text, tool input, tool output),
attributes each event to a phase and prints token estimates per phase, per tool and per file.

Usage:
    python analyse_session.py SESSION.md [--tok-per-s 15] [--chars-per-token 3.6] [--events]

Token estimate: chars / 3.6 (rough average for English prose mixed with code/JSON).
JSON-escaped tool inputs are decoded first, so "\\n" counts as one character.
"Generated" = thinking + assistant text + tool inputs (what the model has to emit).
"Consumed"  = tool outputs (what the model has to read; costs prefill, not decode).
Subagent sessions are not in the export: only their prompt (generated) and summary (consumed).

Timestamps: OpenCode ids are descending (~(ms * 0x1000 + counter), lower 48 bits), so the main
session id and every subagent session id give a time anchor relative to the session start.
"""

import argparse
import json
import re
from datetime import datetime
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

MESSAGE_HEADER = re.compile(r"^## (User|Assistant)\s*$")
TOOL_HEADER = re.compile(r"^\*\*Tool: (\S+)\*\*\s*$")
SESSION_ID = re.compile(r"\*\*Session ID:\*\* ses_([0-9a-f]{12})")
SUBAGENT_ID = re.compile(r'<subagent sessionID="ses_([0-9a-f]{12})')
MAX_48_BITS = 0xFFFFFFFFFFFF


@dataclass
class Event:
    kind: str  # user | thinking | text | tool_input | tool_output
    line: int
    message: int
    chars: int = 0
    tool: str = ""
    args: dict = field(default_factory=dict)
    phase: str = ""
    preview: str = ""


def id_to_ms(hex_id):
    return ((MAX_48_BITS - int(hex_id, 16)) >> 12) & ((1 << 36) - 1)


def decoded_length(raw_json):
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return len(raw_json), {}
    return sum(len(str(v)) for v in data.values()) if isinstance(data, dict) else len(raw_json), (
        data if isinstance(data, dict) else {}
    )


def parse(lines):
    events = []
    message = 0
    role = None
    i = 0
    state = None  # thinking | text | output
    current = None
    blank_run = 0

    def flush():
        nonlocal current
        if current and current.chars > 0:
            events.append(current)
        current = None

    while i < len(lines):
        line = lines[i]
        header = MESSAGE_HEADER.match(line)
        if header:
            flush()
            role = header.group(1)
            message += 1
            state = "user" if role == "User" else "text"
            current = Event("user" if role == "User" else "text", i + 1, message)
            i += 1
            continue
        if role == "Assistant":
            tool = TOOL_HEADER.match(line)
            if tool:
                flush()
                # Input block: **Input:** then ```json ... ```
                j = i + 1
                while j < len(lines) and not lines[j].startswith("```"):
                    j += 1
                k = j + 1
                while k < len(lines) and lines[k] != "```":
                    k += 1
                raw = "\n".join(lines[j + 1 : k])
                chars, args = decoded_length(raw)
                events.append(Event("tool_input", i + 1, message, chars, tool.group(1), args))
                state = "output"
                current = Event("tool_output", k + 2, message, 0, tool.group(1), args)
                i = k + 1
                continue
            if line.strip() == "_Thinking:_":
                flush()
                state = "thinking"
                current = Event("thinking", i + 1, message)
                blank_run = 0
                i += 1
                continue
            if state == "thinking":
                blank_run = blank_run + 1 if not line.strip() else 0
                if blank_run >= 3:  # parts are separated by 3+ blank lines in the export
                    flush()
                    state = "text"
                    current = Event("text", i + 1, message)
        if current is not None and line.strip() != "---":
            current.chars += len(line) + 1 if line.strip() else 0
            if not current.preview and line.strip():
                current.preview = line.strip()[:120]
        i += 1
    flush()
    return events


SKILL_PATH = re.compile(r"(\.agents/skills|explainer-kit|FRAGMENT-CONTRACT|kit\.(css|js)|assemble\.py$|SKILL\.md)")
SHOT = re.compile(r"(chromium|playwright|screenshot|shot[-_]|diag\d*\.js|\.png)")
MEASURE = re.compile(r"(\btime\b|hyperfine|npx |pnpm |oxlint |oxfmt |biome )")
RESEARCH = re.compile(r"(npm view|curl|wget|registry\.npmjs|https?://)")


def path_of(args):
    return str(args.get("path") or args.get("filePath") or args.get("file_path") or "")


def classify(event, state):
    """Phase of one tool call. `state` tracks whether the page was assembled yet."""
    tool, args = event.tool, event.args
    path = path_of(args)
    command = str(args.get("command") or args.get("code") or "")
    content = str(args.get("content") or "")
    if tool == "skill":
        return "1 skills: load"
    if tool in ("websearch", "webfetch"):
        return "3 research: web"
    if tool == "subagent":
        state["subagents"] = True
        return "6 subagents: chapters"
    command = str(args.get("command") or args.get("code") or "")
    touches_output = "/tmp/" in path or "/tmp/" in command
    is_assembly = "assemble.py" in command
    if state.get("subagents") and not state["assembled"] and touches_output and tool != "write" and not is_assembly:
        return "6b fact-check + patch chapters"
    if tool in ("read", "glob", "grep") and SKILL_PATH.search(path):
        return "9 fix loop: re-read kit" if state["assembled"] else "1 skills: read kit/contract"
    if tool in ("write", "edit"):
        if SHOT.search(content) or SHOT.search(path):
            return "8 verify: screenshot scripts"
        if path.endswith("brief.md"):
            return "4 brief"
        if state["assembled"]:
            return "9 fix loop: edit page/fragments"
        return "5 overview/template/fragments (main)"
    if tool in ("shell", "execute", "bash"):
        if "assemble.py" in command:
            state["assembled"] = True
            return "7 assemble"
        if SHOT.search(command):
            return "8 verify: screenshot scripts"
        if tool == "execute" or RESEARCH.search(command):
            return "3 research: web"
        if MEASURE.search(command):
            return "2b repo: measurements"
        if "/tmp/" in command and state["assembled"]:
            return "8 verify: inspect output"
        return "2a repo: exploration"
    if tool in ("read", "glob", "grep"):
        if "/tmp/" in path:
            return "8 verify: inspect output" if state["assembled"] else "5 overview/template/fragments (main)"
        return "2a repo: exploration"
    return "0 other"


def attribute(events):
    state = {"assembled": False}
    by_message = defaultdict(list)
    for event in events:
        by_message[event.message].append(event)
    last_phase = "0 start"
    for message in sorted(by_message):
        group = by_message[message]
        tool_phases = []
        for event in group:
            if event.kind in ("tool_input", "tool_output"):
                if event.kind == "tool_input":
                    event.phase = classify(event, state)
                    tool_phases.append(event.phase)
                else:
                    event.phase = tool_phases[-1]
        # Thinking and text mostly digest the previous tool output, so they belong to its phase
        # (or to the first tool call they lead to, at the very start).
        lead = last_phase if last_phase != "0 start" else (tool_phases[0] if tool_phases else last_phase)
        for event in group:
            if event.kind == "user":
                event.phase = "0 user"
            elif event.kind in ("thinking", "text"):
                event.phase = lead
        if tool_phases:
            last_phase = tool_phases[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("session")
    parser.add_argument("--tok-per-s", type=float, default=15)
    parser.add_argument("--chars-per-token", type=float, default=3.6)
    parser.add_argument("--events", action="store_true", help="also list the 40 biggest events")
    parser.add_argument("--calls", action="store_true", help="also list every tool call with its phase")
    options = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    text = open(options.session, encoding="utf-8").read()
    lines = text.splitlines()
    events = parse(lines)
    attribute(events)
    cpt = options.chars_per_token

    def tok(chars):
        return chars / cpt

    def minutes(chars):
        return tok(chars) / options.tok_per_s / 60

    generated = [e for e in events if e.kind in ("thinking", "text", "tool_input")]
    consumed = [e for e in events if e.kind == "tool_output"]
    gen_total = sum(e.chars for e in generated)
    print(f"Events: {len(events)}  messages: {max(e.message for e in events)}  lines: {len(lines)}")
    print(f"Assumption: tokens = chars / {cpt}; decode speed {options.tok_per_s} tok/s\n")

    kinds = Counter()
    for e in events:
        kinds[e.kind] += e.chars
    print("== By kind ==")
    for kind, chars in kinds.most_common():
        print(f"{kind:12} {tok(chars):9.0f} tok  {minutes(chars):6.1f} min@decode")

    print("\n== Generated tokens by phase (thinking / text / tool input) ==")
    phases = defaultdict(lambda: Counter())
    for e in events:
        phases[e.phase][e.kind] += e.chars
    print(f"{'phase':40} {'think':>7} {'text':>6} {'toolin':>7} {'gen':>7} {'%':>5} {'min':>5} {'consumed':>9}")
    for phase in sorted(phases):
        c = phases[phase]
        gen = c["thinking"] + c["text"] + c["tool_input"]
        print(
            f"{phase:40} {tok(c['thinking']):7.0f} {tok(c['text']):6.0f} {tok(c['tool_input']):7.0f} "
            f"{tok(gen):7.0f} {100 * gen / gen_total:5.1f} {minutes(gen):5.1f} {tok(c['tool_output']):9.0f}"
        )
    print(f"{'TOTAL':40} {'':7} {'':6} {'':7} {tok(gen_total):7.0f} {'100':>5} {minutes(gen_total):5.1f}")

    print("\n== Tool calls ==")
    calls = Counter(e.tool for e in events if e.kind == "tool_input")
    in_chars = Counter()
    out_chars = Counter()
    for e in events:
        if e.kind == "tool_input":
            in_chars[e.tool] += e.chars
        elif e.kind == "tool_output":
            out_chars[e.tool] += e.chars
    for tool_name, count in calls.most_common():
        print(f"{tool_name:10} x{count:3}  input {tok(in_chars[tool_name]):7.0f} tok  output {tok(out_chars[tool_name]):7.0f} tok")

    print("\n== Files written/edited (count, generated tokens) ==")
    files = defaultdict(lambda: [0, 0, 0])
    for e in events:
        if e.kind == "tool_input" and e.tool in ("write", "edit"):
            entry = files[path_of(e.args) or "(no path)"]
            entry[0 if e.tool == "write" else 1] += 1
            entry[2] += e.chars
    for path, (writes, edits, chars) in sorted(files.items(), key=lambda kv: -kv[1][2]):
        print(f"w{writes:2} e{edits:3} {tok(chars):7.0f} tok  {path}")

    print("\n== Files read (count, consumed tokens) ==")
    reads = defaultdict(lambda: [0, 0])
    for e in events:
        if e.kind == "tool_output" and e.tool == "read":
            entry = reads[path_of(e.args)]
            entry[0] += 1
            entry[1] += e.chars
    for path, (count, chars) in sorted(reads.items(), key=lambda kv: -kv[1][1]):
        print(f"x{count:2} {tok(chars):7.0f} tok  {path}")

    print("\n== Failed / erroring tool calls (output starts with an error) ==")
    error = re.compile(r"(error|Error|ERROR|failed|Traceback|not found|No such file|exit code [1-9])")
    for e in events:
        if e.kind == "tool_output" and error.search(e.preview):
            print(f"L{e.line:6} {e.tool:8} {e.preview[:100]}")

    print("\n== Time anchors (from OpenCode session ids) ==")
    main_id = SESSION_ID.search(text)
    if main_id:
        start = id_to_ms(main_id.group(1))
        anchors = [(1, 0.0)]
        for number, line in enumerate(lines, 1):
            sub = SUBAGENT_ID.search(line)
            if sub:
                at = (id_to_ms(sub.group(1)) - start) / 60000
                print(f"L{number:6} subagent started at +{at:6.1f} min")
                if at - anchors[-1][1] > 1:
                    anchors.append((number, at))
        stamps = re.findall(r"\*\*(?:Created|Updated):\*\* (.+)", text)
        if len(stamps) == 2:
            fmt = "%m/%d/%Y, %I:%M:%S %p"
            total = (datetime.strptime(stamps[1], fmt) - datetime.strptime(stamps[0], fmt)).total_seconds() / 60
            anchors.append((len(lines) + 1, total))
        print("\n== Segments between anchors: generated in main thread vs wall clock ==")
        for (from_line, from_min), (to_line, to_min) in zip(anchors, anchors[1:]):
            chars = sum(e.chars for e in generated if from_line <= e.line < to_line)
            print(
                f"L{from_line:6}-L{to_line:6}  wall {to_min - from_min:6.1f} min  "
                f"main generated {tok(chars):7.0f} tok = {minutes(chars):6.1f} min@decode"
            )

    if options.calls:
        print("\n== Tool calls in order ==")
        for e in events:
            if e.kind == "tool_input":
                target = path_of(e.args) or str(e.args.get("command") or e.args.get("query") or e.args.get("url")
                                                 or e.args.get("code") or e.args.get("description") or "")
                print(f"L{e.line:6} {e.tool:9} {tok(e.chars):5.0f} {e.phase:34} {target[:90]!r}")

    if options.events:
        print("\n== 40 biggest generated events ==")
        for e in sorted(generated, key=lambda e: -e.chars)[:40]:
            label = e.tool or e.kind
            target = path_of(e.args) or str(e.args.get("description", ""))[:40]
            print(f"L{e.line:6} {e.kind:10} {label:9} {tok(e.chars):6.0f} tok  {e.phase:34} {target or e.preview[:60]}")


if __name__ == "__main__":
    main()
