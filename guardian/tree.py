"""Load two directory trees (baseline vs proposed) and produce file-level diffs."""
from __future__ import annotations

import difflib
from pathlib import Path

from .models import FileChange

SKIP_DIRS = {".git", "__pycache__", ".venv", "out"}
TEXT_SUFFIXES = {
    ".yaml", ".yml", ".tf", ".hcl", ".json", ".tpl", ".txt", ".md",
    ".rego", ".tmpl",
}


def iter_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != "Jenkinsfile":
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = path
    return files


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def unified(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )


def compare(baseline: Path, proposed: Path) -> list[FileChange]:
    left = iter_files(baseline)
    right = iter_files(proposed)
    changes: list[FileChange] = []
    for rel in sorted(set(left) | set(right)):
        before = read_text(left[rel]) if rel in left else ""
        after = read_text(right[rel]) if rel in right else ""
        if before == after:
            continue
        if rel not in left:
            status = "added"
        elif rel not in right:
            status = "deleted"
        else:
            status = "modified"
        changes.append(
            FileChange(
                path=rel,
                status=status,
                before=before,
                after=after,
                unified_diff=unified(rel, before, after),
            )
        )
    return changes


def apply_contents(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
