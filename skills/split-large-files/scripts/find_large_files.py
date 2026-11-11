"""List agent-facing files that are worth splitting, see ../SKILL.md for the thresholds."""

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

CORE_FILE_NAMES = {"SKILL.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md"}
CORE_MAX_LINES = 300
CORE_MAX_BYTES = 20_000
REFERENCE_MAX_LINES = 500
REFERENCE_MAX_BYTES = 40_000
OTHER_MAX_LINES = 1000
OTHER_MAX_BYTES = 80_000

SKIPPED_DIR_NAMES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "out",
    ".next", ".turbo", "coverage", "target", "archive", "archived",
}
SKIPPED_FILE_NAMES = {"pnpm-lock.yaml", "package-lock.json", "yarn.lock", "uv.lock", "Cargo.lock", "poetry.lock"}
TEXT_SUFFIXES = {
    ".md", ".mdx", ".txt", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".go", ".rs",
    ".java", ".kt", ".cs", ".css", ".scss", ".html", ".sh", ".ps1", ".sql", ".yaml", ".yml", ".toml",
}


@dataclass
class Finding:
    path: str
    kind: str
    lines: int
    kilobytes: float
    reason: str


def is_instruction_file(path: Path) -> bool:
    return path.name in CORE_FILE_NAMES or (path.suffix == ".md" and "instructions" in path.parts)


def is_skill_reference(path: Path) -> bool:
    return path.suffix == ".md" and path.name != "SKILL.md" and find_skill_dir(path) is not None


def find_skill_dir(path: Path) -> Path | None:
    for parent in path.parents:
        if (parent / "SKILL.md").is_file():
            return parent
    return None


def measure(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    return data.count(b"\n") + 1, len(data)


def walk(root: Path):
    for dir_path, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name not in SKIPPED_DIR_NAMES]
        for name in file_names:
            if name not in SKIPPED_FILE_NAMES:
                yield Path(dir_path) / name


def over(lines: int, size: int, max_lines: int, max_bytes: int) -> str | None:
    if lines > max_lines or size > max_bytes:
        return f"over {max_lines} lines or {max_bytes // 1000} KB"
    return None


def unmentioned_references(skill_md: Path) -> list[Path]:
    skill_dir = skill_md.parent
    skill_text = skill_md.read_text(encoding="utf-8", errors="replace")
    references = [path for path in skill_dir.rglob("*.md") if path != skill_md and find_skill_dir(path) == skill_dir]
    return [
        path for path in references
        if not re.search(re.escape(path.relative_to(skill_dir).as_posix()), skill_text)
        and path.name not in skill_text
    ]


def scan(root: Path, include_all: bool) -> list[Finding]:
    findings: list[Finding] = []
    for path in walk(root):
        if path.suffix not in TEXT_SUFFIXES and path.name not in CORE_FILE_NAMES:
            continue
        lines, size = measure(path)
        if is_instruction_file(path):
            kind, reason = "core", over(lines, size, CORE_MAX_LINES, CORE_MAX_BYTES)
        elif is_skill_reference(path):
            kind, reason = "reference", over(lines, size, REFERENCE_MAX_LINES, REFERENCE_MAX_BYTES)
        elif include_all:
            kind, reason = "other", over(lines, size, OTHER_MAX_LINES, OTHER_MAX_BYTES)
        else:
            continue
        if reason:
            findings.append(Finding(str(path), kind, lines, round(size / 1000, 1), reason))
        if path.name == "SKILL.md":
            for reference in unmentioned_references(path):
                ref_lines, ref_size = measure(reference)
                findings.append(Finding(
                    str(reference), "unmentioned", ref_lines, round(ref_size / 1000, 1),
                    f"not mentioned in {path}",
                ))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--all", action="store_true", help="also list other large text files, e.g. code")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    findings = [finding for root in args.roots for finding in scan(root, args.all)]
    findings.sort(key=lambda finding: (finding.kind == "unmentioned", -finding.kilobytes))

    if args.json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    elif not findings:
        print("No large agent-facing files found.")
    else:
        for finding in findings:
            print(f"{finding.kind:<12} {finding.lines:>6} lines {finding.kilobytes:>7} KB  {finding.path}  ({finding.reason})")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
