#!/usr/bin/env python3
"""Build example review pages for three kinds of change, to see and test how the page looks.

    python build_examples.py OUT_DIR [--artifact]

Each example makes its "before" in a scratch folder under OUT_DIR/work, starts a review session or a repo, makes the
change, fills in the FILE and CHANGE notes and renders OUT_DIR/<name>.html:

- code-fix: a branch in a small repo that moves invoice totals from float to Decimal.
- ops-change: a backup script and its config outside any repo, a scheduled task read with a command, a command run
  through `review.py run` and a Notion change recorded with `review.py note`.
- reorganise: a Downloads folder sorted into subfolders, found as moves by content.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REVIEW = Path(__file__).resolve().parent.parent / "assets" / "review.py"
PYTHON = "python" if shutil.which("python") else f'"{sys.executable}"'


def review(*args: str) -> None:
    subprocess.run([sys.executable, str(REVIEW), *args], check=True, stdout=subprocess.DEVNULL)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=Example", "-c", "user.email=example@example.com", "-C", str(repo), *args],
                   check=True, capture_output=True)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8")


def annotate(sources: list[str], template: Path, summaries: dict[str, str], notes: dict[str, str]) -> None:
    """Write the notes template with `outline`, then fill it in: `summaries` by path, `notes` by a piece of the
    change's first changed line, so the example doesn't depend on line numbers."""
    review("outline", *sources, "--template", str(template))
    data = json.loads(template.read_text(encoding="utf-8"))
    for path, entry in data.items():
        if path.startswith("_"):
            continue
        entry["summary"] = summaries.get(path, "")
        for item in entry["changes"]:
            item["text"] = next((text for piece, text in notes.items() if piece in item["line"]), "")
    template.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def render(sources: list[str], work: Path, out: Path, title: str, description: str, artifact: bool) -> None:
    write(work / "description.md", description)
    review("render", *sources, "--annotations", str(work / "notes.json"), "--description",
           str(work / "description.md"), "--title", title, "--out", str(out), *(["--artifact"] if artifact else []))
    print(f"Wrote {out}")


INVOICE_BEFORE = '''
from dataclasses import dataclass


@dataclass
class Line:
    description: str
    quantity: int
    unit_price: float


def line_total(line: Line) -> float:
    return line.quantity * line.unit_price


def invoice_total(lines: list[Line], vat_rate: float = 0.25) -> float:
    subtotal = sum(line_total(line) for line in lines)
    return round(subtotal * (1 + vat_rate), 2)


def format_amount(amount: float) -> str:
    return f"kr {amount:.2f}"
'''

INVOICE_AFTER = '''
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass
class Line:
    description: str
    quantity: int
    unit_price: Decimal


def line_total(line: Line) -> Decimal:
    return (line.quantity * line.unit_price).quantize(CENT, rounding=ROUND_HALF_UP)


def invoice_total(lines: list[Line], vat_rate: Decimal = Decimal("0.25")) -> Decimal:
    subtotal = sum((line_total(line) for line in lines), Decimal("0"))
    return (subtotal * (1 + vat_rate)).quantize(CENT, rounding=ROUND_HALF_UP)


def format_amount(amount: Decimal) -> str:
    return f"kr {amount:.2f}".replace(".", ",")
'''


def code_fix(work: Path, out: Path, artifact: bool) -> None:
    origin, repo = work / "invoice-service.git", work / "invoice-service"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    write(repo / "invoice.py", INVOICE_BEFORE)
    write(repo / "README.md", "# Invoice service\n\nTotals are rounded to two decimals with `round()`.\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "feat: invoice totals")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "remote", "set-head", "origin", "main")
    git(repo, "switch", "-q", "-c", "fix/invoice-rounding")
    write(repo / "invoice.py", INVOICE_AFTER)
    git(repo, "commit", "-q", "-am", "fix(invoice): use Decimal and round each line half up")
    write(repo / "test_invoice.py", '''
from decimal import Decimal

from invoice import Line, format_amount, invoice_total


def test_rounds_each_line_half_up():
    lines = [Line("Coffee", 3, Decimal("33.335")), Line("Milk", 1, Decimal("19.90"))]
    assert invoice_total(lines) == Decimal("149.89")


def test_formats_with_norwegian_decimal_comma():
    assert format_amount(Decimal("149.89")) == "kr 149,89"
''')
    write(repo / "README.md", "# Invoice service\n\nAmounts are `Decimal`. Each line is rounded half up to whole øre "
                              "before VAT, as on a printed receipt.\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "test(invoice): rounding and formatting")
    git(repo, "push", "-q", "origin", "fix/invoice-rounding")
    sources = ["--git", str(repo)]
    annotate(sources, work / "notes.json", {
        "invoice.py": "Amounts move from `float` to `Decimal`, so totals no longer pick up binary rounding errors.",
        "test_invoice.py": "New tests for the two cases the customer reported.",
        "README.md": "Says how amounts are rounded now.",
    }, {
        "from decimal import ROUND": "`CENT` is the step every amount is rounded to.",
        "unit_price: float": "Callers must now pass `Decimal`. All three call sites already parse prices from "
                             "strings.",
        "def line_total": "Each line is rounded on its own, half up, like the receipt the customer compared with.",
        "def invoice_total": "`sum` gets a `Decimal` start value, or an empty invoice would return the int `0`.",
        "def format_amount": "Norwegian decimal comma, which the PDF template used to add by itself.",
    })
    render(sources, work, out, "Fix rounding in invoice totals", '''
A customer's invoice was 1 øre off their own sum: kr 149.88, where their receipt said kr 149,89.

**Background:** totals were rounded only once, after VAT, and a `float` can't hold 33.335 exactly.

**Fixed:** amounts are `Decimal` instead of `float`, and each line is rounded half up before VAT, so 3 × 33.335 is
100.01, as on the receipt. Amounts print with a decimal comma, and two tests cover both cases. Two commits on
`fix/invoice-rounding`, pushed, not merged.
''', artifact)


def ops_change(work: Path, out: Path, artifact: bool) -> None:
    scripts, session = work / "scripts", work / "review"
    write(scripts / "backup.ps1", '''
$source = "C:\\Users\\me\\Documents"
$target = "E:\\Backup\\Documents"
robocopy $source $target /MIR /R:2 /W:5 /LOG:"$PSScriptRoot\\logs\\backup.log"
''')
    write(scripts / "backup.json", '''
{
  "target": "E:\\\\Backup",
  "keepDays": 14,
  "notify": false
}
''')
    write(scripts / "old-backup.bat", "xcopy C:\\Users\\me\\Documents E:\\Backup\\Documents /E /Y\n")
    write(scripts / "logs" / "2026-10.log", "2026-10-31 02:00 OK 1 204 files\n")
    write(work / "tasks.csv", '"Backup","02:00","Ready"\n"Defrag","Sunday 04:00","Ready"\n')
    write(work / "schtasks.py", '''
"""Stands in for Windows' schtasks in this example: /query prints tasks.csv, /change sets a task's time."""
import sys
from pathlib import Path

tasks = Path(__file__).with_name("tasks.csv")
if sys.argv[1] == "/query":
    print(tasks.read_text(), end="")
else:
    name, time = sys.argv[sys.argv.index("/tn") + 1], sys.argv[sys.argv.index("/st") + 1]
    lines = [f'"{name}","{time}","Ready"' if line.startswith(f'"{name}"') else line
             for line in tasks.read_text().splitlines()]
    tasks.write_text("\\n".join(lines) + "\\n")
    print(f'SUCCESS: The parameters of scheduled task "{name}" have been changed.')
''')
    review("begin", str(session), "--title", "Move nightly backup to D:", "--files", str(scripts),
           "--capture", f"tasks={PYTHON} schtasks.py /query", "--cwd", str(work))
    write(scripts / "backup.ps1", '''
$config = Get-Content "$PSScriptRoot\\backup.json" | ConvertFrom-Json
$source = "C:\\Users\\me\\Documents"
$target = Join-Path $config.target "Documents"
robocopy $source $target /MIR /R:2 /W:5 /LOG:"$PSScriptRoot\\logs\\backup.log"
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with $LASTEXITCODE" }
''')
    write(scripts / "backup.json", '''
{
  "target": "D:\\\\Backup",
  "keepDays": 30,
  "notify": false
}
''')
    (scripts / "old-backup.bat").unlink()
    (scripts / "archive").mkdir()
    (scripts / "logs" / "2026-10.log").rename(scripts / "archive" / "2026-10.log")
    review("run", str(session), f"{PYTHON} schtasks.py /change /tn Backup /st 03:00", "--cwd", str(work))
    write(work / "notion-result.json", '{"page_id": "40f1…", "properties": {"Status": "Pågår"}}\n')
    review("note", str(session), "--title", "Set Status to Pågår on the task “Flytte backup til D:”",
           "--body", "Through the Notion MCP, `notion-update-page`.", "--evidence", str(work / "notion-result.json"))
    sources = ["--session", str(session)]
    annotate(sources, work / "notes.json", {
        "backup.ps1": "Reads the target from `backup.json` instead of hard-coding it, and fails loudly.",
        "backup.json": "The new disk, and a longer history since D: has room for it.",
        "old-backup.bat": "Replaced by `backup.ps1` last year and not scheduled anywhere.",
        "tasks": "The backup now starts after the 02:30 Windows Update window.",
    }, {
        "$config": "One place to change the disk next time.",
        "$target": "The path now comes from the config.",
        "LASTEXITCODE": "robocopy exit codes 8 and up are errors; 1–7 mean files were copied.",
        '"target"': "E: is the old USB disk that keeps disconnecting.",
        '"Backup","02:00"': "Moved by the `schtasks /change` below.",
    })
    render(sources, work, out, "Move nightly backup to D:", '''
The nightly backup wrote to E:, a USB disk that disconnects, so three of the last ten runs failed.

**Background:** the script, its config and the scheduled task live outside any repo, so this page compares snapshots
taken before the change.

**Fixed:** it writes to the internal D: disk, reads the target from `backup.json` and fails when robocopy does. The
scheduled task runs at 03:00 instead of 02:00, after the Windows Update window. The unused `xcopy` script is deleted
and last month's log moved to `archive/`.
''', artifact)


def reorganise(work: Path, out: Path, artifact: bool) -> None:
    downloads, session = work / "Downloads", work / "review"
    files = {
        "IMG_2041.jpg": b"\xff\xd8\xff photo 1",
        "IMG_2042.jpg": b"\xff\xd8\xff photo 2",
        "Strømregning oktober.pdf": b"%PDF-1.7 power bill",
        "Lønnsslipp oktober.pdf": b"%PDF-1.7 payslip",
        "setup-node-24.msi": b"MSI installer",
        "notes.txt": "Ting å kjøpe:\n- batterier\n- pærer\n",
        "notes (1).txt": "Ting å kjøpe:\n- batterier\n- pærer\n",
    }
    for name, data in files.items():
        path = downloads / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data) if isinstance(data, bytes) else path.write_text(data, encoding="utf-8")
    review("begin", str(session), "--title", "Sort the Downloads folder", "--files", str(downloads))
    moves = {
        "IMG_2041.jpg": "Bilder/2026-10/IMG_2041.jpg",
        "IMG_2042.jpg": "Bilder/2026-10/IMG_2042.jpg",
        "Strømregning oktober.pdf": "Regninger/2026/Strømregning oktober.pdf",
        "Lønnsslipp oktober.pdf": "Jobb/Lønnsslipper/2026-10.pdf",
        "setup-node-24.msi": "Installere/setup-node-24.msi",
    }
    for old, new in moves.items():
        (downloads / new).parent.mkdir(parents=True, exist_ok=True)
        (downloads / old).rename(downloads / new)
    (downloads / "notes (1).txt").unlink()
    write(downloads / "notes.txt", "Ting å kjøpe:\n- batterier (AA)\n- pærer\n- lim\n")
    sources = ["--session", str(session)]
    annotate(sources, work / "notes.json", {
        "notes (1).txt": "An exact copy of `notes.txt`, the browser's second download of it.",
        "notes.txt": "The user's additions from the chat, kept in the one remaining copy.",
        "Jobb/Lønnsslipper/2026-10.pdf": "Renamed to the month, like the other payslips in that folder.",
    }, {
        "batterier": "AA, as the user asked.",
    })
    render(sources, work, out, "Sort the Downloads folder", '''
Downloads had 140 files in one folder, so nothing could be found there.

**Background:** moves are found by content, so a moved file shows as a move, not as a delete and an add.

**Changed:** the files are sorted into Bilder, Regninger, Jobb and Installere, the same folders as in OneDrive. An
exact duplicate of `notes.txt` is deleted, and the remaining copy has the shopping items from the chat. This example
shows a handful of the files.
''', artifact)


# What each example must show: the files and their status in the overview, how many of them moved, the description
# labels that get their own line, and which stat boxes must and mustn't be there.
EXPECTED = {
    "code-fix": {
        "files": {"README.md": "modified", "invoice.py": "modified", "test_invoice.py": "added"}, "moves": 0,
        "labels": ["Background:", "Fixed:"], "tests": True,
        "stats": ["files changed", "lines", "generated"],
        "no_stats": ["repos and folders", "checked states changed", "commands run", "reported by agent", "machine"]},
    "ops-change": {
        "files": {"archive/2026-10.log": "moved", "backup.json": "modified", "backup.ps1": "modified",
                  "old-backup.bat": "deleted", "tasks": "modified"}, "moves": 1,
        "labels": ["Background:", "Fixed:"], 
        "stats": ["checked states changed", "commands run", "reported by agent", "session started"],
        "no_stats": ["repos and folders"]},
    "reorganise": {
        "files": {"Bilder/2026-10/IMG_2041.jpg": "moved", "Bilder/2026-10/IMG_2042.jpg": "moved",
                  "Regninger/2026/Strømregning oktober.pdf": "moved", "Jobb/Lønnsslipper/2026-10.pdf": "moved",
                  "Installere/setup-node-24.msi": "moved", "notes (1).txt": "deleted", "notes.txt": "modified"},
        "moves": 5, "labels": ["Background:", "Changed:"], "stats": ["files changed", "session started"],
        "no_stats": ["commands run", "checked states changed"]},
}


def file_versions(name: str, work: Path) -> dict[str, tuple[list[str], list[str]]]:
    """Each changed file's lines before and after, read from the example's own sources (git, or the session's
    snapshot and the files on disk), not from the page, so the page's diff can be checked against them."""
    versions = {}
    if name == "code-fix":
        repo = work / "invoice-service"
        for path in EXPECTED[name]["files"]:
            shown = subprocess.run(["git", "-C", str(repo), "show", f"main:{path}"], capture_output=True, text=True,
                                   encoding="utf-8")
            after = repo / path
            versions[path] = (shown.stdout.splitlines() if shown.returncode == 0 else [],
                              after.read_text(encoding="utf-8").splitlines() if after.exists() else [])
        return versions
    session = json.loads((work / "review" / "session.json").read_text(encoding="utf-8"))
    for watch in session["watches"]:
        root = Path(watch["root"])
        manifest = json.loads((work / "review" / f"{watch['id']}.before.json").read_text(encoding="utf-8"))
        for path in EXPECTED[name]["files"]:
            blob = work / "review" / "blobs" / manifest[path]["sha"] if path in manifest else None
            before = blob.read_text(encoding="utf-8", errors="replace").splitlines() if blob and blob.exists() else []
            after = ((root / path).read_text(encoding="utf-8", errors="replace").splitlines()
                     if (root / path).is_file() else [])
            versions[path] = (before, after)
    for capture in session["captures"]:
        before = json.loads((work / "review" / f"{capture['id']}.before.json").read_text(encoding="utf-8"))
        versions[capture["name"]] = (before["output"].splitlines(), (work / "tasks.csv").read_text().splitlines())
    return versions


def check_page(name: str, page: Path, work: Path) -> list[str]:
    """What's wrong with the example's page, as a list; empty when it shows what it should."""
    html = page.read_text(encoding="utf-8")
    expected = EXPECTED[name]
    problems = []
    # The page escapes apostrophes in some warnings, so match on text without one.
    for warning, problem in (("Notes that couldn", "some notes couldn't be placed"),
                             ("Notes for files that aren", "some notes are for files that aren't on the page")):
        if warning in html:
            problems.append(f"the page warns that {problem}")
    notes = json.loads((work / "notes.json").read_text(encoding="utf-8"))
    summaries = sum(bool(entry["summary"]) for path, entry in notes.items() if not path.startswith("_"))
    changes = sum(bool(item["text"]) for path, entry in notes.items() if not path.startswith("_")
                  for item in entry["changes"])
    for label, count in (("file", summaries), ("change", changes)):
        shown = html.count(f"rv-annot-tag'>{label}</span>")
        if shown != count:
            problems.append(f"{shown} {label.upper()} notes on the page, {count} written")
    places = [html.find(f"<strong>{label}</strong><br>") for label in expected["labels"]]
    for label, place in zip(expected["labels"], places):
        if place < 0:
            problems.append(f"the description's {label} isn't on its own line")
    if all(place >= 0 for place in places) and places != sorted(places):
        problems.append(f"the description's labels aren't in the order {expected['labels']}")
    for stat in expected["stats"]:
        if f"</b>{stat}</div>" not in html:
            problems.append(f"no '{stat}' box")
    for stat in expected["no_stats"]:
        if f"</b>{stat}</div>" in html:
            problems.append(f"a '{stat}' box that shouldn't be there")
    sections = len(re.findall(r"<details class='rv-file' id='s\d+-\d+'", html))
    listed = html.count("class='rv-toc-file'")
    if listed != sections:
        problems.append(f"{listed} files in the contents list, {sections} file sections on the page")
    if '<button id="rv-wrap" aria-pressed="true"' not in html:
        problems.append("no 'Wrap lines' button that starts on")
    # The files and their status, from each file section's heading.
    sections = {html_module.unescape(path): (status, body) for path, status, body in re.findall(
        r"<details class='rv-file' id='[^']+' data-path='([^']*)'(?: open)?><summary><span class='rv-chip rv-(\w+)'"
        r"(.*?)</details>", html, re.S)}
    files = {path: status for path, (status, _) in sections.items()}
    if files != expected["files"]:
        problems.append(f"the page shows {files}, expected {expected['files']}")
    moves = sum(status == "moved" for status in files.values())
    if moves != expected["moves"]:
        problems.append(f"{moves} files moved on the page, expected {expected['moves']}")
    if expected.get("tests"):
        repo = work / "invoice-service"
        run = subprocess.run([sys.executable, "-c", "import test_invoice as t; [getattr(t, n)() for n in dir(t) "
                              "if n.startswith('test_')]"], cwd=repo, capture_output=True, text=True)
        if run.returncode != 0:
            problems.append(f"the example's own tests fail: {run.stderr.strip().splitlines()[-1]}")
    # Every line of the diff, as the "Old + new" view shows it, must be in the old or new file it claims.
    versions = file_versions(name, work)
    checked = 0
    for path, (_, body) in sections.items():
        before, after = versions.get(path, ([], []))
        for kind, code in re.findall(r"<tr class='rv-(add|del|ctx)(?: rv-only-lines)?'>.*?<td class='rv-code'>"
                                     r"<span class='rv-sign'>.</span>(.*?)</td></tr>", body, re.S):
            text = html_module.unescape(re.sub(r"</?(?:del|ins)>", "", code))
            checked += 1
            if kind in ("ctx", "del") and text not in before:
                problems.append(f"the diff of {path} shows an old line that isn't in the old file: {text!r}")
            if kind in ("ctx", "add") and text not in after:
                problems.append(f"the diff of {path} shows a new line that isn't in the new file: {text!r}")
    if not checked:
        problems.append("no diff lines found to check")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", help="Folder for the pages; its work/ subfolder is replaced")
    parser.add_argument("--artifact", action="store_true", help="Render for the Artifact tool, see review.py")
    parser.add_argument("--check", action="store_true",
                        help="Check each page against the example's own sources, and exit 1 on a problem")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    if (out / "work").exists():
        # git's object files are read-only, which stops rmtree on Windows.
        shutil.rmtree(out / "work", onerror=lambda func, path, _: (os.chmod(path, stat.S_IWRITE), func(path)))
    failed = False
    for name, build in (("code-fix", code_fix), ("ops-change", ops_change), ("reorganise", reorganise)):
        work = out / "work" / name
        work.mkdir(parents=True)
        build(work, out / f"{name}.html", args.artifact)
        if args.check:
            problems = check_page(name, out / f"{name}.html", work)
            print(f"  {'ok' if not problems else 'FAILED'}: {name}")
            for problem in problems:
                print(f"    - {problem}")
            failed = failed or bool(problems)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
