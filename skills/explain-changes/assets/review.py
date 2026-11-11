#!/usr/bin/env python3
"""Build a review page of changes from git, file snapshots and recorded commands.

Everything on the page comes from git, the file system or commands this script ran, never from what an agent
remembers, except the description and the FILE and CHANGE notes. See ../SKILL.md for how to use it.

Running shell commands is part of the job, and they only ever come from the person or agent running the script:
`run COMMAND` runs and records one command, and `begin --capture NAME=COMMAND` runs a read-only command whose
output is diffed. `render` runs those capture commands once more from the session's session.json, which `begin`
wrote, so render only sessions you started yourself. Nothing is downloaded or sent anywhere: the page is a local file.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import hashlib
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

SNAPSHOT_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".next", "dist", ".turbo"}
MAX_TEXT_BYTES = 1_000_000
MAX_SNAPSHOT_FILES = 20_000
MAX_DIFF_LINES_PER_FILE = 3_000
MAX_OUTPUT_CHARS = 20_000
COLLAPSE_ABOVE_CHANGED_LINES = 400
GENERATED_FILE_PATTERN = re.compile(
    r"(^|/)(pnpm-lock\.yaml|package-lock\.json|yarn\.lock|Cargo\.lock|poetry\.lock|uv\.lock|[^/]+\.min\.(js|css))$"
)
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
WORD_TOKEN = re.compile(r"\w+|\s+|[^\w\s]")
# A removed and an added line count as one modified line when this share of their words match.
MIN_LINE_SIMILARITY = 0.5
MAX_WORD_DIFF_CHARS = 2_000


# ---------- shared model ----------


def new_file_change(path: str, status: str, old_path: str | None = None) -> dict:
    return {"path": path, "old_path": old_path, "status": status, "hunks": [], "added": 0, "removed": 0,
            "note": None, "truncated": False, "summary": None, "stray_notes": []}


def parse_hunks(diff_lines: list[str], change: dict) -> None:
    """Fill change["hunks"] from unified diff lines that start at or before the first @@ header."""
    hunk = None
    old_no = new_no = 0
    shown = 0
    for line in diff_lines:
        match = HUNK_HEADER.match(line)
        if match:
            old_no, new_no = int(match.group(1)), int(match.group(3))
            hunk = {"header": line, "lines": [], "notes": {},
                    "old": (old_no, int(match.group(2) or 1)), "new": (new_no, int(match.group(4) or 1))}
            change["hunks"].append(hunk)
            continue
        if hunk is None or line.startswith("\\ No newline"):
            continue
        kind = line[:1]
        text = line[1:]
        if kind == "+":
            change["added"] += 1
            row = ("add", None, new_no, text)
            new_no += 1
        elif kind == "-":
            change["removed"] += 1
            row = ("del", old_no, None, text)
            old_no += 1
        else:
            row = ("ctx", old_no, new_no, text)
            old_no += 1
            new_no += 1
        if shown < MAX_DIFF_LINES_PER_FILE:
            hunk["lines"].append(row)
            shown += 1
        else:
            change["truncated"] = True


def text_diff(old_text: str, new_text: str, change: dict) -> None:
    lines = list(difflib.unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm="", n=3))
    parse_hunks(lines[2:], change)


def decode_text(data: bytes) -> str | None:
    if b"\0" in data[:8000] or len(data) > MAX_TEXT_BYTES:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def run(cmd: list[str] | str, cwd: str | Path | None = None, shell: bool = False, check: bool = True,
        timeout: int = 300) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, shell=shell, capture_output=True, timeout=timeout,
                            encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise SystemExit(f"Command failed ({result.returncode}): {cmd}\n{result.stderr.strip()}")
    return result


def short_time(iso: str) -> str:
    """"5 Nov 18:54" from an ISO time, or the text as it is if it isn't one."""
    try:
        moment = datetime.datetime.fromisoformat(iso)
    except ValueError:
        return esc(iso)
    return f"{moment.day} {moment:%b} {moment:%H:%M}"


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ---------- git ----------


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", "-c", "core.quotepath=false", "-C", str(repo), *args], check=check).stdout


def default_base(repo: Path) -> str:
    head = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", check=False).strip()
    if head:
        return head.removeprefix("refs/remotes/")
    for candidate in ("origin/main", "origin/master", "main", "master"):
        if run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", candidate], check=False).returncode == 0:
            return candidate
    raise SystemExit(f"No base branch found in {repo}; pass --git PATH=BASE")


def github_web_url(remote_url: str) -> str | None:
    match = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?/?$", remote_url.strip())
    return f"https://github.com/{match.group(1)}" if match else None


def path_from_diff_git_line(line: str) -> str:
    both = line[len("diff --git "):]
    return both[2:2 + (len(both) - 5) // 2]


def parse_git_patch(patch: str) -> list[dict]:
    changes = []
    blocks = re.split(r"(?m)^(?=diff --git )", patch)
    for block in blocks:
        if not block.startswith("diff --git "):
            continue
        lines = block.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        header_end = next((i for i, line in enumerate(lines) if line.startswith("@@")), len(lines))
        header = lines[:header_end]
        old_path = new_path = None
        status = "modified"
        binary = False
        for line in header:
            if line.startswith("new file mode"):
                status = "added"
            elif line.startswith("deleted file mode"):
                status = "deleted"
            elif line.startswith("rename from "):
                old_path, status = line[len("rename from "):], "renamed"
            elif line.startswith("rename to "):
                new_path = line[len("rename to "):]
            elif line.startswith("--- a/"):
                old_path = old_path or line[len("--- a/"):]
            elif line.startswith("+++ b/"):
                new_path = line[len("+++ b/"):]
            elif line.startswith("Binary files"):
                binary = True
        fallback = path_from_diff_git_line(lines[0])
        path = new_path or old_path or fallback
        change = new_file_change(path, status, old_path if status == "renamed" else None)
        if binary:
            change["note"] = "Binary file changed"
        parse_hunks(lines[header_end:], change)
        changes.append(change)
    return changes


def untracked_changes(repo: Path) -> list[dict]:
    changes = []
    for rel in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if not rel:
            continue
        change = new_file_change(rel, "added")
        data = (repo / rel).read_bytes()
        text = decode_text(data)
        if text is None:
            change["note"] = f"Untracked binary or large file ({len(data):,} bytes)"
        else:
            text_diff("", text, change)
        change["untracked"] = True
        changes.append(change)
    return changes


def collect_git(spec: str) -> dict:
    path_text, _, base = spec.partition("=")
    repo = Path(git(Path(path_text), "rev-parse", "--show-toplevel").strip())
    base = base or default_base(repo)
    merge_base = git(repo, "merge-base", base, "HEAD").strip()
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    head = git(repo, "rev-parse", "--short", "HEAD").strip()
    commits = []
    for line in git(repo, "log", "--format=%h%x09%ad%x09%an%x09%s", "--date=short", f"{merge_base}..HEAD").splitlines():
        sha, date, author, subject = line.split("\t", 3)
        commits.append({"sha": sha, "date": date, "author": author, "subject": subject})
    patch = git(repo, "diff", "--no-color", "--no-ext-diff", "-M", "-U3", "--src-prefix=a/", "--dst-prefix=b/",
                merge_base)
    changes = parse_git_patch(patch) + untracked_changes(repo)
    uncommitted = [line[3:] for line in git(repo, "status", "--porcelain").splitlines() if line]
    remote = git(repo, "remote", "get-url", "origin", check=False).strip()
    web = github_web_url(remote) if remote else None
    pushed = None
    compare_url = None
    if branch != "HEAD":
        remote_branch = f"origin/{branch}"
        if run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", remote_branch], check=False).returncode == 0:
            pushed = {"unpushed": int(git(repo, "rev-list", "--count", f"{remote_branch}..HEAD").strip() or 0)}
            if web:
                compare_url = f"{web}/compare/{base.removeprefix('origin/')}...{branch}"
    last_part = remote.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    remote_name = re.sub(r"\.git$", "", last_part) if remote else ""
    return {"kind": "git", "name": remote_name or repo.name, "path": str(repo), "base": base, "merge_base": merge_base[:7],
            "branch": branch, "head": head, "commits": commits, "changes": changes, "uncommitted": uncommitted,
            "web": web, "compare_url": compare_url, "pushed": pushed}


# ---------- session: file and command snapshots ----------


def load_session(session_dir: Path) -> dict:
    session_file = session_dir / "session.json"
    if not session_file.exists():
        raise SystemExit(f"No review session in {session_dir}; run `begin` first")
    return json.loads(session_file.read_text(encoding="utf-8"))


def save_session(session_dir: Path, session: dict) -> None:
    (session_dir / "session.json").write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


def walk_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SNAPSHOT_SKIP_DIRS)
        for filename in sorted(filenames):
            found.append(Path(dirpath) / filename)
            if len(found) > MAX_SNAPSHOT_FILES:
                raise SystemExit(f"More than {MAX_SNAPSHOT_FILES} files under {root}; watch a narrower folder")
    return found


def snapshot_files(root: Path, blob_dir: Path | None) -> dict:
    manifest = {}
    for file in walk_files(root):
        rel = file.name if root.is_file() else file.relative_to(root).as_posix()
        data = file.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        manifest[rel] = {"sha": sha, "size": len(data)}
        if blob_dir is not None and decode_text(data) is not None:
            blob_dir.mkdir(parents=True, exist_ok=True)
            blob = blob_dir / sha
            if not blob.exists():
                blob.write_bytes(data)
    return manifest


def run_capture(command: str, cwd: str | None) -> dict:
    result = run(command, cwd=cwd, shell=True, check=False)
    return {"exit": result.returncode, "output": result.stdout + (result.stderr and f"\n[stderr]\n{result.stderr}")}


def cmd_begin(args: argparse.Namespace) -> None:
    session_dir = Path(args.session)
    if (session_dir / "session.json").exists():
        raise SystemExit(f"{session_dir} already has a session; use a new folder")
    session_dir.mkdir(parents=True, exist_ok=True)
    session = {"title": args.title or session_dir.name, "created": now_iso(), "machine": platform.node(),
               "watches": [], "captures": [], "gits": args.git or []}
    for index, path_text in enumerate(args.files or []):
        root = Path(path_text).resolve()
        watch_id = f"w{index}"
        manifest = snapshot_files(root, session_dir / "blobs")
        (session_dir / f"{watch_id}.before.json").write_text(json.dumps(manifest), encoding="utf-8")
        session["watches"].append({"id": watch_id, "root": str(root), "is_file": root.is_file(),
                                   "existed": root.exists()})
    for index, spec in enumerate(args.capture or []):
        name, _, command = spec.partition("=")
        if not command:
            raise SystemExit(f"--capture needs NAME=COMMAND, got {spec!r}")
        capture_id = f"c{index}"
        before = run_capture(command, args.cwd)
        (session_dir / f"{capture_id}.before.json").write_text(json.dumps(before), encoding="utf-8")
        session["captures"].append({"id": capture_id, "name": name, "command": command, "cwd": args.cwd})
    save_session(session_dir, session)
    print(f"Review session started in {session_dir}: {len(session['watches'])} watched paths, "
          f"{len(session['captures'])} captured commands")


def append_action(session_dir: Path, action: dict) -> None:
    with (session_dir / "actions.jsonl").open("a", encoding="utf-8") as actions:
        actions.write(json.dumps(action, ensure_ascii=False) + "\n")


def cmd_run(args: argparse.Namespace) -> None:
    session_dir = Path(args.session)
    load_session(session_dir)
    started = now_iso()
    result = run(args.command, cwd=args.cwd, shell=True, check=False, timeout=args.timeout)
    append_action(session_dir, {"kind": "run", "command": args.command, "cwd": args.cwd or os.getcwd(),
                                "started": started, "exit": result.returncode,
                                "stdout": result.stdout[-MAX_OUTPUT_CHARS:],
                                "stderr": result.stderr[-MAX_OUTPUT_CHARS:]})
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    sys.exit(result.returncode)


def cmd_note(args: argparse.Namespace) -> None:
    session_dir = Path(args.session)
    load_session(session_dir)
    evidence = None
    if args.evidence:
        evidence = Path(args.evidence).read_text(encoding="utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
    append_action(session_dir, {"kind": "note", "title": args.title, "body": args.body or "",
                                "evidence_file": args.evidence, "evidence": evidence, "time": now_iso()})
    print("Noted")


def diff_watch(session_dir: Path, watch: dict) -> dict:
    root = Path(watch["root"])
    before = json.loads((session_dir / f"{watch['id']}.before.json").read_text(encoding="utf-8"))
    after = snapshot_files(root, None)
    blobs = session_dir / "blobs"
    changes = []
    deleted = {rel: meta for rel, meta in before.items() if rel not in after}
    added = {rel: meta for rel, meta in after.items() if rel not in before}
    for rel, meta in list(added.items()):
        moved_from = next((old for old, old_meta in deleted.items() if old_meta["sha"] == meta["sha"]), None)
        if moved_from:
            changes.append(new_file_change(rel, "renamed", moved_from))
            del deleted[moved_from], added[rel]
    for rel in added:
        change = new_file_change(rel, "added")
        data = (root if root.is_file() else root / rel).read_bytes()
        text = decode_text(data)
        if text is None:
            change["note"] = f"Binary or large file ({len(data):,} bytes)"
        else:
            text_diff("", text, change)
        changes.append(change)
    for rel, meta in deleted.items():
        change = new_file_change(rel, "deleted")
        blob = blobs / meta["sha"]
        if blob.exists():
            text_diff(blob.read_text(encoding="utf-8"), "", change)
        else:
            change["note"] = f"Binary or large file ({meta['size']:,} bytes)"
        changes.append(change)
    for rel in sorted(set(before) & set(after)):
        if before[rel]["sha"] == after[rel]["sha"]:
            continue
        change = new_file_change(rel, "modified")
        blob = blobs / before[rel]["sha"]
        new_text = decode_text((root if root.is_file() else root / rel).read_bytes())
        if blob.exists() and new_text is not None:
            text_diff(blob.read_text(encoding="utf-8"), new_text, change)
        else:
            change["note"] = (f"Binary or large file changed ({before[rel]['size']:,} → "
                              f"{after[rel]['size']:,} bytes)")
        changes.append(change)
    changes.sort(key=lambda change: change["path"])
    return {"kind": "files", "name": root.name, "path": str(root), "changes": changes,
            "unchanged": len(set(before) & set(after)) - sum(c["status"] == "modified" for c in changes)}


def diff_capture(session_dir: Path, capture: dict) -> dict:
    before = json.loads((session_dir / f"{capture['id']}.before.json").read_text(encoding="utf-8"))
    after = run_capture(capture["command"], capture["cwd"])
    change = new_file_change(capture["name"], "modified")
    text_diff(before["output"], after["output"], change)
    return {**capture, "before_exit": before["exit"], "after_exit": after["exit"], "change": change,
            "unchanged": before["output"] == after["output"], "after_output": after["output"][:MAX_OUTPUT_CHARS]}


# ---------- rendering ----------

STATUS_GLYPH = {"added": ("+", "added"), "deleted": ("−", "deleted"), "modified": ("~", "modified"),
                "renamed": ("→", "moved")}


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def inline_markdown(text: str) -> str:
    text = esc(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)


def render_markdown(markdown: str) -> str:
    """A small subset: headings, bullets, code fences, paragraphs, inline code, bold and links."""
    out, in_list, in_code, code, para = [], False, False, [], []

    def flush() -> None:
        if para:
            text = inline_markdown(' '.join(para))
            # A paragraph that starts with a bold label ("**Fixed:** ...") gets the label on its own line, and the
            # text after it a capital letter.
            text = re.sub(r"^(<strong>[^<]{1,40}:</strong>)\s*(\w?)",
                          lambda m: f"{m.group(1)}<br>{m.group(2).upper()}", text)
            out.append(f"<p>{text}</p>")
            para.clear()

    for line in markdown.splitlines():
        if not in_code and (not line.strip() or re.match(r"^(#{1,4} |\s*[-*] |```)", line)):
            flush()
        if line.startswith("```"):
            if in_code:
                out.append(f"<pre class='rv-pre'>{esc(chr(10).join(code))}</pre>")
                code = []
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        bullet = re.match(r"^\s*[-*] (.*)$", line)
        if in_list and not bullet:
            out.append("</ul>")
            in_list = False
        heading = re.match(r"^(#{1,4}) (.*)$", line)
        if heading:
            level = min(len(heading.group(1)) + 2, 6)
            out.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
        elif bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline_markdown(bullet.group(1))}</li>")
        elif line.strip():
            para.append(line.strip())
    flush()
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append(f"<pre class='rv-pre'>{esc(chr(10).join(code))}</pre>")
    return "\n".join(out)


def word_segments(old: str, new: str) -> list[tuple[str, str]] | None:
    """The two lines as ("eq" | "del" | "ins", text) pieces, or None when they differ too much to be one modified
    line."""
    if len(old) + len(new) > MAX_WORD_DIFF_CHARS:
        return None
    a, b = WORD_TOKEN.findall(old), WORD_TOKEN.findall(new)
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if matcher.ratio() < MIN_LINE_SIMILARITY:
        return None
    segments = []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            segments.append(("eq", "".join(a[i1:i2])))
            continue
        if i2 > i1:
            segments.append(("del", "".join(a[i1:i2])))
        if j2 > j1:
            segments.append(("ins", "".join(b[j1:j2])))
    return segments


def segments_html(segments: list[tuple[str, str]]) -> tuple[str, str, str]:
    """The old line, the new line and the two merged, as HTML with the changed words marked."""
    mark = lambda kind, text: esc(text) if kind == "eq" else f"<{kind}>{esc(text)}</{kind}>"
    return ("".join(mark(k, t) for k, t in segments if k != "ins"),
            "".join(mark(k, t) for k, t in segments if k != "del"),
            "".join(mark(k, t) for k, t in segments))


def diff_row(kind: str, old_no: int | None, new_no: int | None, code_html: str, view: str = "") -> str:
    sign = {"add": "+", "del": "−", "ctx": " ", "mod": "~"}[kind]
    view_class = f" rv-only-{view}" if view else ""
    # On narrow screens only the second number column shows, and a removed line shows its old number there.
    old_hint = f" data-old='{old_no}'" if kind == "del" else ""
    return (f"<tr class='rv-{kind}{view_class}'><td class='rv-no rv-no-old'>{old_no or ''}</td>"
            f"<td class='rv-no rv-no-new'{old_hint}>{new_no or ''}</td><td class='rv-code'><span class='rv-sign'>{sign}</span>{code_html}</td></tr>")


def change_blocks(hunk: dict) -> list[tuple[int, str]]:
    """Each run of changed lines in the hunk, as (index of its first line, its anchor). The anchor is the first
    changed line: -N in the old file when the run starts with a removed line, otherwise +N in the new file."""
    blocks = []
    for index, (kind, old_no, new_no, _) in enumerate(hunk["lines"]):
        if kind != "ctx" and (index == 0 or hunk["lines"][index - 1][0] == "ctx"):
            blocks.append((index, f"-{old_no}" if kind == "del" else f"+{new_no}"))
    return blocks


def note_row(text: str) -> str:
    return f"<tr class='rv-annot-row'><td colspan='3'>{agent_note(text, 'change')}</td></tr>"


def hunk_rows(lines: list[tuple], notes: dict[int, list[str]] | None = None) -> list[str]:
    """Rows for both views: "lines" shows removed then added lines, "inline" shows a modified line once with the
    removed words red and the added words green. Rows that look the same in both views are emitted once. The notes
    for a run of changed lines go right above its first line."""
    notes = notes or {}
    rows, index = [], 0
    while index < len(lines):
        rows.extend(note_row(text) for text in notes.get(index, []))
        if lines[index][0] != "del":
            kind, old_no, new_no, text = lines[index]
            rows.append(diff_row(kind, old_no, new_no, esc(text)))
            index += 1
            continue
        dels, adds = [], []
        while index < len(lines) and lines[index][0] == "del":
            dels.append(lines[index])
            index += 1
        while index < len(lines) and lines[index][0] == "add":
            adds.append(lines[index])
            index += 1
        pairs = {i: (k, segments_html(segments))
                 for i, (k, segments) in pair_lines([d[3] for d in dels], [a[3] for a in adds]).items()}
        if not pairs:
            rows.extend(diff_row(kind, old_no, new_no, esc(text)) for kind, old_no, new_no, text in dels + adds)
            continue
        by_add = {k: (i, diff) for i, (k, diff) in pairs.items()}
        for i, (_, old_no, _, text) in enumerate(dels):
            rows.append(diff_row("del", old_no, None, pairs[i][1][0] if i in pairs else esc(text), "lines"))
        for k, (_, _, new_no, text) in enumerate(adds):
            rows.append(diff_row("add", None, new_no, by_add[k][1][1] if k in by_add else esc(text), "lines"))
        next_add = 0
        for i, (_, old_no, _, text) in enumerate(dels):
            if i not in pairs:
                rows.append(diff_row("del", old_no, None, esc(text), "inline"))
                continue
            k, diff = pairs[i]
            rows.extend(diff_row("add", None, adds[j][2], esc(adds[j][3]), "inline") for j in range(next_add, k))
            rows.append(diff_row("mod", old_no, adds[k][2], diff[2], "inline"))
            next_add = k + 1
        rows.extend(diff_row("add", None, adds[j][2], esc(adds[j][3]), "inline") for j in range(next_add, len(adds)))
    return rows


def pair_lines(old: list[str], new: list[str]) -> dict[int, tuple[int, list[tuple[str, str]]]]:
    """Match each removed line with the first similar enough added line after the previous match, keeping order,
    so a line that moved down a few rows (an item inserted above it) still pairs with its new version."""
    pairs, start = {}, 0
    search_all = len(old) * len(new) <= 2_500
    for i, line in enumerate(old):
        candidates = range(start, len(new)) if search_all else [i] if i < len(new) else []
        for k in candidates:
            segments = word_segments(line, new[k])
            if segments:
                pairs[i] = (k, segments)
                start = k + 1
                break
    return pairs


def agent_note(text: str, kind: str) -> str:
    """A note the agent wrote, about a whole file ("file") or one run of changed lines ("change")."""
    return (f"<div class='rv-annot rv-annot-{kind}'><span class='rv-annot-tag'>{kind}</span> "
            f"{inline_markdown(text)}</div>")


def render_change(change: dict, anchor: str) -> str:
    change["anchor"] = anchor
    glyph, label = STATUS_GLYPH.get(change["status"], ("~", change["status"]))
    changed_lines = change["added"] + change["removed"]
    collapsed = (changed_lines > COLLAPSE_ABOVE_CHANGED_LINES or GENERATED_FILE_PATTERN.search(change["path"])
                 or change["status"] == "deleted")
    title = esc(change["path"])
    if change.get("old_path"):
        title = f"<span class='rv-old'>{esc(change['old_path'])}</span> → {title}"
    extras = []
    if change.get("untracked"):
        extras.append("<span class='rv-tag'>untracked</span>")
    if GENERATED_FILE_PATTERN.search(change["path"]):
        extras.append("<span class='rv-tag'>generated</span>")
    rows = []
    for hunk in change["hunks"]:
        rows.append(f"<tr class='rv-hunk'><td colspan='3'>{esc(hunk['header'])}</td></tr>")
        rows.extend(hunk_rows(hunk["lines"], hunk["notes"]))
    body = ""
    if change["summary"]:
        body += agent_note(change["summary"], "file")
    if change["stray_notes"]:
        body += ("<p class='rv-note rv-warn'>! Notes that couldn't be placed in this file: "
                 f"{esc('; '.join(change['stray_notes']))}</p>")
    if rows:
        body += f"<div class='rv-scroll'><table class='rv-diff'>{''.join(rows)}</table></div>"
    if change["note"]:
        body += f"<p class='rv-note'>{esc(change['note'])}</p>"
    elif not rows:
        body += "<p class='rv-note'>Moved without content changes.</p>" if change["status"] == "renamed" else \
            "<p class='rv-note'>No line changes (mode or empty file).</p>"
    if change["truncated"]:
        body += f"<p class='rv-note'>Showing the first {MAX_DIFF_LINES_PER_FILE:,} lines of this diff.</p>"
    viewed_key = f"{esc(anchor)}:{esc(change['path'])}:{change['added']}:{change['removed']}"
    # The same actions again below a diff, so a long one can be marked and folded without scrolling back up.
    if rows:
        body += (f"<div class='rv-file-foot'><label class='rv-viewed'><input type='checkbox' data-key='{viewed_key}'> "
                 "Viewed</label><button type='button' class='rv-fold'>Collapse ↑</button></div>")
    return (f"<details class='rv-file' id='{anchor}' data-path='{esc(change['path'])}'{'' if collapsed else ' open'}>"
            f"<summary><span class='rv-chip rv-{label}' title='{label}'>{glyph}</span>"
            f"<span class='rv-path'>{title}</span>{''.join(extras)}"
            f"<span class='rv-count'><span class='rv-plus'>+{change['added']}</span> "
            f"<span class='rv-minus'>−{change['removed']}</span></span>"
            f"<label class='rv-viewed' onclick='event.stopPropagation()'><input type='checkbox' "
            f"data-key='{viewed_key}'> Viewed</label>"
            f"</summary>{body}</details>")


def render_file_list(changes: list[dict], prefix: str) -> str:
    items = []
    for index, change in enumerate(changes):
        glyph, label = STATUS_GLYPH.get(change["status"], ("~", change["status"]))
        summary = f"<span class='rv-desc'>{inline_markdown(change['summary'])}</span>" if change["summary"] else ""
        items.append(f"<li><a href='#{prefix}-{index}'><span class='rv-chip rv-{label}'>{glyph}</span>"
                     f"<span class='rv-fl'><span class='rv-path'>{esc(change['path'])}</span>{summary}</span></a>"
                     f"<span class='rv-count'>"
                     f"<span class='rv-plus'>+{change['added']}</span> <span class='rv-minus'>−{change['removed']}"
                     f"</span></span></li>")
    return f"<ul class='rv-files'>{''.join(items)}</ul>"


def totals(changes: list[dict]) -> tuple[int, int, int]:
    return len(changes), sum(c["added"] for c in changes), sum(c["removed"] for c in changes)


def render_source(source: dict, index: int) -> tuple[str, str]:
    prefix = f"s{index}"
    files, added, removed = totals(source["changes"])
    parts = []
    if source["kind"] == "git":
        heading = f"{esc(source['name'])} <span class='rv-muted'>{esc(source['branch'])} vs {esc(source['base'])}</span>"
        facts = [f"<code>{esc(source['path'])}</code>", f"merge base <code>{esc(source['merge_base'])}</code>",
                 f"HEAD <code>{esc(source['head'])}</code>"]
        if source["pushed"] is not None:
            facts.append("pushed" if source["pushed"]["unpushed"] == 0 else
                         f"<strong class='rv-warn'>! {source['pushed']['unpushed']} commits not pushed</strong>")
        elif source["branch"] != "HEAD":
            facts.append("<strong class='rv-warn'>! branch not on origin</strong>")
        if source["uncommitted"]:
            facts.append(f"<strong class='rv-warn'>! {len(source['uncommitted'])} uncommitted files, "
                         "included below</strong>")
        links = []
        if source["compare_url"]:
            links.append(f"<a class='rv-button' href='{esc(source['compare_url'])}'>Open on GitHub ↗</a>")
        parts.append(f"<p class='rv-facts'>{' · '.join(facts)}</p>{''.join(links)}")
        if source["commits"]:
            rows = "".join(f"<tr><td><code>{esc(c['sha'])}</code></td><td>{esc(c['date'])}</td>"
                           f"<td>{esc(c['subject'])}</td></tr>" for c in source["commits"])
            parts.append(f"<details class='rv-commits'><summary>{len(source['commits'])} commits</summary>"
                         f"<table class='rv-table'>{rows}</table></details>")
    else:
        heading = f"{esc(source['name'])} <span class='rv-muted'>files, before vs after</span>"
        parts.append(f"<p class='rv-facts'><code>{esc(source['path'])}</code> · {source['unchanged']} files unchanged</p>")
    summary = f"{files} files <span class='rv-plus'>+{added}</span> <span class='rv-minus'>−{removed}</span>"
    if not source["changes"]:
        parts.append("<p class='rv-note'>No changes.</p>")
    else:
        parts.append(render_file_list(source["changes"], prefix))
        parts.extend(render_change(change, f"{prefix}-{i}") for i, change in enumerate(source["changes"]))
    section = (f"<section class='rv-section' id='{prefix}'><h2>{heading}</h2><p class='rv-sum'>{summary}</p>"
               f"{''.join(parts)}</section>")
    # The contents list names each changed file under its repo or folder: the file name, or the whole path when
    # two files share a name.
    names = [Path(change["path"]).name for change in source["changes"]]
    entries = "".join(
        f"<li><a class='rv-toc-file' href='#{prefix}-{i}' title='{esc(change['path'])}'>"
        f"<span class='rv-chip rv-{STATUS_GLYPH.get(change['status'], ('~', change['status']))[1]}'>"
        f"{STATUS_GLYPH.get(change['status'], ('~', ''))[0]}</span>"
        f"{esc(change['path'] if names.count(names[i]) > 1 else names[i])}</a></li>"
        for i, change in enumerate(source["changes"]))
    toc = (f"<li><a href='#{prefix}'>{esc(source['name'])}</a> <span class='rv-muted'>{files}</span>"
           f"{f'<ul>{entries}</ul>' if entries else ''}</li>")
    return section, toc


def render_captures(captures: list[dict]) -> str:
    items = []
    for index, capture in enumerate(captures):
        state = "unchanged" if capture["unchanged"] else f"+{capture['change']['added']} −{capture['change']['removed']}"
        exits = f"exit {capture['before_exit']} → {capture['after_exit']}"
        body = (render_change(capture["change"], f"c{index}") if not capture["unchanged"] else
                f"<details class='rv-file'><summary><span class='rv-path'>Current output</span></summary>"
                f"<pre class='rv-pre'>{esc(capture['after_output'])}</pre></details>")
        items.append(f"<div class='rv-capture'><h3>{esc(capture['name'])} <span class='rv-muted'>{state} · {exits}"
                     f"</span></h3><p class='rv-facts'><code>{esc(capture['command'])}</code></p>{body}</div>")
    return (f"<section class='rv-section' id='captures'><h2>State before vs after</h2><p class='rv-sum'>Output of "
            f"commands captured at the start and again now.</p>{''.join(items)}</section>")


def render_actions(actions: list[dict]) -> str:
    items = []
    for action in actions:
        if action["kind"] == "run":
            ok = "ok" if action["exit"] == 0 else "risk"
            output = action["stdout"] + (f"\n[stderr]\n{action['stderr']}" if action["stderr"] else "")
            items.append(f"<li class='rv-action'><span class='rv-chip rv-{ok}'>{'✓' if ok == 'ok' else '!'}</span>"
                         f"<div><code class='rv-cmd'>{esc(action['command'])}</code><p class='rv-muted'>"
                         f"{esc(action['started'])} · exit {action['exit']} · in <code>{esc(action['cwd'])}</code></p>"
                         f"<details><summary>Output</summary><pre class='rv-pre'>{esc(output or '(none)')}</pre>"
                         f"</details></div></li>")
        else:
            evidence = ""
            if action.get("evidence") is not None:
                evidence = (f"<details><summary title='{esc(action['evidence_file'])}'>Evidence: "
                        f"{esc(Path(action['evidence_file']).name)}</summary>"
                            f"<pre class='rv-pre'>{esc(action['evidence'])}</pre></details>")
            items.append(f"<li class='rv-action'><span class='rv-chip rv-agent'>A</span><div><strong>"
                         f"{esc(action['title'])}</strong> <span class='rv-tag'>reported by agent</span>"
                         f"<p>{inline_markdown(action['body'])}</p>{evidence}</div></li>")
    return (f"<section class='rv-section' id='actions'><h2>Actions</h2><p class='rv-sum'>Commands run through "
            f"<code>review.py run</code> are recorded as they ran; items marked “reported by agent” are not.</p>"
            f"<ul class='rv-actions'>{''.join(items)}</ul></section>")


# The page's style and script live next to this file, so the script stays short enough to read and audit.
CSS = (Path(__file__).parent / "review.css").read_text(encoding="utf-8")
SCRIPT = (Path(__file__).parent / "review.js").read_text(encoding="utf-8")


def render_page(title: str, sources: list[dict], captures: list[dict], actions: list[dict], description: str | None,
                created: str | None, for_artifact: bool, warnings: list[str]) -> str:
    warnings_html = "".join(f"<p class='rv-note rv-warn'>! {esc(warning)}</p>" for warning in warnings)
    sections, toc = [], []
    for index, source in enumerate(sources):
        section, toc_item = render_source(source, index)
        sections.append(section)
        toc.append(toc_item)
    all_changes = [change for source in sources for change in source["changes"]]
    files, added, removed = totals(all_changes)
    changed_captures = sum(not capture["unchanged"] for capture in captures)
    if captures:
        sections.append(render_captures(captures))
        toc.append(f"<li><a href='#captures'>State before vs after</a> <span class='rv-muted'>{changed_captures}"
                   f"</span></li>")
    if actions:
        sections.append(render_actions(actions))
        toc.append(f"<li><a href='#actions'>Actions</a> <span class='rv-muted'>{len(actions)}</span></li>")
    description_html = f"<div class='rv-description'>{render_markdown(description)}</div>" if description else ""
    stat = lambda value, label, tip="": (f"<div class='rv-stat'{f' title={chr(39)}{esc(tip)}{chr(39)}' if tip else ''}>"
                                         f"<b>{value}</b>{label}</div>")
    stats = [stat(files, "files changed"),
             stat(f"<span class='rv-plus'>+{added}</span> <span class='rv-minus'>−{removed}</span>", "lines")]
    if len(sources) > 1:
        stats.append(stat(len(sources), "repos and folders"))
    if captures:
        stats.append(stat(f"{changed_captures} of {len(captures)}", "checked states changed",
                          "Output of read-only commands, e.g. a scheduled task list, captured before and after"))
    commands = sum(action["kind"] == "run" for action in actions)
    if commands:
        stats.append(stat(commands, "commands run", "Run through review.py run, with exit code and output"))
    if len(actions) - commands:
        stats.append(stat(len(actions) - commands, "reported by agent",
                          "Actions the script couldn't record itself, e.g. a Notion update"))
    if created:
        stats.append(stat(short_time(created), "session started"))
    stats.append(stat(short_time(now_iso()), "generated"))
    if for_artifact:
        opening = (f'<title>{esc(title)}</title><meta name="claude:viewport-fit-sides" content="cover">'
                   f'<style>{CSS}</style>')
        closing = ""
    else:
        opening = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
                   f'content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{CSS}</style>'
                   f'</head><body>')
        closing = "</body></html>"
    return f"""{opening}
<div class="rv-layout"><nav class="rv-nav"><strong>Contents</strong><ul>{''.join(toc)}</ul></nav>
<main><header><h1>{esc(title)}</h1>{description_html}
<div class="rv-hero">{''.join(stats)}
<span class="rv-info" tabindex="0" role="button" aria-label="Where this page comes from" aria-describedby="rv-source">i</span>
<span class="rv-tip" id="rv-source" role="tooltip">The diffs, file lists, states and commands come from git, file
snapshots and the commands themselves, computed by <code>review.py</code>. The agent wrote
{"the description above, " if description else ""}the FILE and CHANGE notes and anything marked “reported by
agent”.</span></div>
</header>
<div class="rv-toolbar"><div class="rv-tools"><div class="rv-seg" role="group" aria-label="Diff view"><button data-mode="inline"
aria-pressed="true" title="A changed line once, removed words red and added words green">Inline</button><button
data-mode="lines" aria-pressed="false" title="Removed lines, then added lines">Old + new</button></div>
<button id="rv-wrap" aria-pressed="true" title="Wrap long lines instead of scrolling sideways">Wrap lines</button><button id="rv-expand">Expand all</button><button id="rv-collapse">Collapse all</button></div></div>
{warnings_html}{''.join(sections)}</main></div><script>{SCRIPT}</script>{closing}
"""


def collect(args: argparse.Namespace) -> tuple[dict | None, list[dict], list[dict], list[dict]]:
    session = None
    session_dir = Path(args.session) if args.session else None
    if session_dir:
        session = load_session(session_dir)
    sources = [collect_git(spec) for spec in [*(session["gits"] if session else []), *(args.git or [])]]
    captures, actions = [], []
    if session:
        sources.extend(diff_watch(session_dir, watch) for watch in session["watches"])
        captures = [diff_capture(session_dir, capture) for capture in session["captures"]]
        actions_file = session_dir / "actions.jsonl"
        if actions_file.exists():
            actions = [json.loads(line) for line in actions_file.read_text(encoding="utf-8").splitlines() if line]
    if not sources and not captures and not actions:
        raise SystemExit("Nothing to review: pass --git PATH or --session DIR")
    return session, sources, captures, actions


def reviewable_changes(sources: list[dict], captures: list[dict]) -> list[dict]:
    return ([change for source in sources for change in source["changes"]] +
            [capture["change"] for capture in captures if not capture["unchanged"]])


def block_text(hunk: dict, start: int) -> str:
    return hunk["lines"][start][3].strip()[:80]


def find_block(change: dict, anchor: str) -> tuple[dict, int] | None:
    """The run of changed lines a note's "at" points to: the run that starts there, else the run that contains that
    line, else the first run of the hunk around it."""
    match = re.fullmatch(r"([+-]?)(\d+)", anchor.strip())
    if not match:
        return None
    old_side, line = match.group(1) == "-", int(match.group(2))
    anchor = f"{'-' if old_side else '+'}{line}"
    runs = [(hunk, start, block_anchor) for hunk in change["hunks"] for start, block_anchor in change_blocks(hunk)]
    for hunk, start, block_anchor in runs:
        if block_anchor == anchor:
            return hunk, start
    for hunk, start, _ in runs:
        index = start
        while index < len(hunk["lines"]) and hunk["lines"][index][0] != "ctx":
            kind, old_no, new_no, _ = hunk["lines"][index]
            if (old_no if old_side else new_no) == line:
                return hunk, start
            index += 1
    for hunk, start, _ in runs:
        first, count = hunk["old"] if old_side else hunk["new"]
        if first <= line < first + max(count, 1):
            return hunk, start
    return None


def apply_annotations(changes: list[dict], annotations: dict) -> list[str]:
    """Attach the agent's per-file summaries and per-change notes. Returns warnings for notes that match nothing,
    so a stale note shows up instead of vanishing."""
    used = set()
    for change in changes:
        entry = annotations.get(change["path"])
        if not isinstance(entry, dict):
            continue
        used.add(change["path"])
        change["summary"] = (entry.get("summary") or "").strip() or None
        for item in entry.get("changes") or []:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            found = find_block(change, str(item.get("at", "")))
            if not found:
                change["stray_notes"].append(f"{item.get('at')}: {text}")
                continue
            hunk, start = found
            hunk["notes"].setdefault(start, []).append(text)
    unknown = [path for path, entry in annotations.items()
               if not path.startswith("_") and path not in used and isinstance(entry, dict)
               and ((entry.get("summary") or "").strip() or any((i.get("text") or "").strip()
                                                                for i in entry.get("changes") or []))]
    return [f"Notes for files that aren't on this page: {', '.join(unknown)}"] if unknown else []


def cmd_outline(args: argparse.Namespace) -> None:
    _, sources, captures, _ = collect(args)
    changes = reviewable_changes(sources, captures)
    for change in changes:
        print(f"{change['status'][:1].upper()} {change['path']}  +{change['added']} −{change['removed']}")
        for hunk in change["hunks"]:
            for start, anchor in change_blocks(hunk):
                print(f"    {anchor:>7}  {block_text(hunk, start)}")
    if not args.template:
        return
    template_path = Path(args.template)
    existing = json.loads(template_path.read_text(encoding="utf-8")) if template_path.exists() else {}
    template = {"_help": "Fill in 'summary' per file and 'text' per change, a sentence each: what and why, not a "
                         "retelling of the diff. Leave a value empty to skip it. 'at' is the change's first changed "
                         "line, +N in the new file or -N in the old; 'line' is only there to help you."}
    for change in changes:
        old = existing.get(change["path"]) if isinstance(existing.get(change["path"]), dict) else {}
        kept = [item for item in old.get("changes") or [] if (item.get("text") or "").strip()]
        kept_anchors = {item.get("at") for item in kept}
        fresh = [{"at": anchor, "line": block_text(hunk, start), "text": ""}
                 for hunk in change["hunks"] for start, anchor in change_blocks(hunk) if anchor not in kept_anchors]
        template[change["path"]] = {"summary": old.get("summary", ""), "changes": kept + fresh}
    for path, entry in existing.items():
        template.setdefault(path, entry)
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {template_path}")


def cmd_render(args: argparse.Namespace) -> None:
    session, sources, captures, actions = collect(args)
    warnings = []
    if args.annotations:
        warnings = apply_annotations(reviewable_changes(sources, captures),
                                     json.loads(Path(args.annotations).read_text(encoding="utf-8")))
    description = Path(args.description).read_text(encoding="utf-8") if args.description else None
    title = args.title or (session["title"] if session else f"Review of {', '.join(s['name'] for s in sources)}")
    page = render_page(title, sources, captures, actions, description, session["created"] if session else None,
                       args.artifact, warnings)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    files, added, removed = totals([c for s in sources for c in s["changes"]])
    print(f"Wrote {out} ({len(page):,} bytes): {files} files, +{added} −{removed}, "
          f"{sum(not c['unchanged'] for c in captures)}/{len(captures)} states changed, {len(actions)} actions")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command_name", required=True)

    begin = commands.add_parser("begin", help="Snapshot files and command output before you change anything")
    begin.add_argument("session", help="A new folder for this review session, e.g. in your scratchpad")
    begin.add_argument("--title")
    begin.add_argument("--files", action="append", metavar="PATH", help="A file or folder to snapshot (repeatable)")
    begin.add_argument("--capture", action="append", metavar="NAME=COMMAND",
                       help="A command whose output is the state to compare, e.g. 'cron=crontab -l' (repeatable)")
    begin.add_argument("--cwd", help="Working folder for --capture commands")
    begin.add_argument("--git", action="append", metavar="PATH[=BASE]", help="A repo to include (repeatable)")
    begin.set_defaults(handler=cmd_begin)

    run_parser = commands.add_parser("run", help="Run a command and record it, its exit code and output")
    run_parser.add_argument("session")
    run_parser.add_argument("command", help="The command line, run through the shell")
    run_parser.add_argument("--cwd")
    run_parser.add_argument("--timeout", type=int, default=600)
    run_parser.set_defaults(handler=cmd_run)

    note = commands.add_parser("note", help="Record an action the script couldn't run, e.g. an MCP tool call")
    note.add_argument("session")
    note.add_argument("--title", required=True)
    note.add_argument("--body")
    note.add_argument("--evidence", metavar="FILE", help="A file with the raw tool result, included verbatim")
    note.set_defaults(handler=cmd_note)

    outline = commands.add_parser("outline", help="List the changed files and changes, and write a template for "
                                                  "the agent's per-file and per-change notes")
    outline.add_argument("--session")
    outline.add_argument("--git", action="append", metavar="PATH[=BASE]")
    outline.add_argument("--template", metavar="FILE",
                         help="Write or update this annotations JSON; notes already filled in are kept")
    outline.set_defaults(handler=cmd_outline)

    render = commands.add_parser("render", help="Compare against now and write the review page")
    render.add_argument("--session")
    render.add_argument("--git", action="append", metavar="PATH[=BASE]",
                        help="A repo: its branch vs BASE (default origin/HEAD), committed and uncommitted (repeatable)")
    render.add_argument("--description", metavar="FILE",
                        help="Markdown shown under the title: why the change was made and a little background")
    render.add_argument("--annotations", metavar="FILE",
                        help="JSON from 'outline --template' with a summary per file and a note per change")
    render.add_argument("--title")
    render.add_argument("--out", required=True)
    render.add_argument("--artifact", action="store_true",
                        help="Leave out the document skeleton, which the Artifact tool adds when it publishes")
    render.set_defaults(handler=cmd_render)

    args = parser.parse_args()
    if not shutil.which("git") and getattr(args, "git", None):
        raise SystemExit("git is not on PATH")
    args.handler(args)


if __name__ == "__main__":
    main()
