"""Build a single unified diff the reviewer can apply. Never applied to a cluster."""
from __future__ import annotations

from .detectors import apply_finding_patches
from .models import FileChange, Finding
from .tree import unified


def suggested_files(changes: list[FileChange], findings: list[Finding]) -> dict[str, str]:
    """Return proposed-path → safer content, chaining patches per file."""
    ids = {f.id for f in findings}
    by_path: dict[str, str] = {}
    for ch in changes:
        by_path[ch.path] = apply_finding_patches(ch.path, ch.before, ch.after, ids)
    return by_path


def suggested_unified_diff(changes: list[FileChange], findings: list[Finding]) -> str:
    files = suggested_files(changes, findings)
    parts: list[str] = []
    for ch in changes:
        safer = files.get(ch.path)
        if safer is None or safer == ch.after:
            continue
        parts.append(unified(ch.path, ch.after, safer))
    return "".join(parts)
