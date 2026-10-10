"""Lightweight parsers for Helm values, Kubernetes YAML, and Terraform HCL snippets."""
from __future__ import annotations

import re
from typing import Any


def parse_memory_mi(value: str) -> int | None:
    raw = value.strip().strip('"').strip("'")
    if not raw:
        return None
    lower = raw.lower()
    try:
        if lower.endswith("gi"):
            return int(float(raw[:-2]) * 1024)
        if lower.endswith("mi"):
            return int(float(raw[:-2]))
        if lower.endswith("ki"):
            return max(1, int(float(raw[:-2]) / 1024))
        if lower.endswith("g"):
            return int(float(raw[:-1]) * 1024)
        if lower.endswith("m") and not lower.endswith("mi"):
            # megabytes (not millicores — callers should only pass memory fields)
            return int(float(raw[:-1]))
        if raw.isdigit():
            return max(1, int(raw) // (1024 * 1024))
    except ValueError:
        return None
    return None


def parse_indent_map(text: str) -> dict:
    """Parse a subset of YAML mappings/scalars used by Helm values and simple manifests."""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        m = re.match(r"^(\s*)([^:#\s][^:]*):\s*(.*?)\s*$", line)
        if not m:
            continue
        key, val = m.group(2).strip(), m.group(3)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if val == "" or val in ("|", ">"):
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = val.strip().strip('"').strip("'")
    return root


def yaml_get(text: str, dotted: str) -> str | None:
    """Return a scalar at a dotted path. Dots in keys are not supported."""
    cur: object = parse_indent_map(text)
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    if isinstance(cur, dict):
        return None
    return str(cur)


def yaml_line_of(text: str, key: str, value_substr: str | None = None) -> int | None:
    for i, line in enumerate(text.splitlines(), start=1):
        if key in line and (value_substr is None or value_substr in line):
            return i
    return None


def snippet_at(text: str, line_no: int | None, radius: int = 2) -> str:
    if not line_no:
        return text.strip()[:240]
    lines = text.splitlines()
    start = max(0, line_no - 1 - radius)
    end = min(len(lines), line_no + radius)
    numbered = []
    for i in range(start, end):
        mark = ">" if i + 1 == line_no else " "
        numbered.append(f"{mark} {i + 1:4d} | {lines[i]}")
    return "\n".join(numbered)


def hcl_string_assigns(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for m in re.finditer(
        r'(internal|load_balancer_type|scheme)\s*=\s*"([^"]+)"', text
    ):
        found[m.group(1)] = m.group(2)
    return found


def iam_actions_and_resources(text: str) -> dict[str, Any]:
    """Collect IAM Action/Resource values, skipping sts:AssumeRole trust policies."""
    actions: list[str] = []
    resources: list[str] = []
    for m in re.finditer(r"Action\s*=\s*(\[[^\]]*\]|\"[^\"]+\")", text, re.DOTALL):
        found = re.findall(r'"([^"]+)"', m.group(1))
        if found == ["sts:AssumeRole"]:
            continue
        actions.extend(found)
    for m in re.finditer(r"Resource\s*=\s*(\[[^\]]*\]|\"[^\"]+\")", text, re.DOTALL):
        resources.extend(re.findall(r'"([^"]+)"', m.group(1)))
    return {"actions": actions, "resources": resources}


def is_wildcard(value: str) -> bool:
    return value == "*" or value.endswith(":*") or value.endswith(":*:*")
