"""Deterministic risk detectors. Findings are produced from the diff and files,
not from the LLM — the model only explains what these functions already found.
"""
from __future__ import annotations

from .models import Evidence, FileChange, Finding
from .parse import (
    hcl_string_assigns,
    iam_actions_and_resources,
    is_wildcard,
    parse_memory_mi,
    snippet_at,
    yaml_get,
    yaml_line_of,
)

# Floors used by the demo policy (mirrors policies/*.rego).
MIN_LIMIT_MI = 256
MIN_REQUEST_MI = 128


def detect(changes: list[FileChange]) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_memory(changes))
    findings.extend(_public_lb(changes))
    findings.extend(_iam(changes))
    return findings


def apply_finding_patches(path: str, before: str, current: str, finding_ids: set[str]) -> str:
    """Apply detector patches in sequence so two findings on one file both land."""
    text = current
    if "REL-MEM-001" in finding_ids and _is_yaml(path):
        restore = yaml_get(before, "resources.limits.memory") or "1Gi"
        restore_req = yaml_get(before, "resources.requests.memory") or "512Mi"
        ch = FileChange(path=path, status="modified", before=before, after=text, unified_diff="")
        text = _memory_patch(ch, restore_req, restore)
    if "SEC-LB-002" in finding_ids:
        ch = FileChange(path=path, status="modified", before=before, after=text, unified_diff="")
        text = _lb_patch(ch)
    if "SEC-IAM-003" in finding_ids and path.endswith(".tf"):
        ch = FileChange(path=path, status="modified", before=before, after=text, unified_diff="")
        parsed = iam_actions_and_resources(before)
        text = _iam_patch(ch, parsed if parsed["actions"] else None)
    return text


def _memory(changes: list[FileChange]) -> list[Finding]:
    out: list[Finding] = []
    for ch in changes:
        if not _is_yaml(ch.path):
            continue
        after_limit = yaml_get(ch.after, "resources.limits.memory")
        after_req = yaml_get(ch.after, "resources.requests.memory")
        before_limit = yaml_get(ch.before, "resources.limits.memory")
        if after_limit is None and after_req is None:
            continue
        after_mi = parse_memory_mi(after_limit or "") if after_limit else None
        before_mi = parse_memory_mi(before_limit or "") if before_limit else None
        req_mi = parse_memory_mi(after_req or "") if after_req else None
        risky = False
        reasons = []
        if after_mi is not None and after_mi < MIN_LIMIT_MI:
            risky = True
            reasons.append(
                f"memory limit {after_limit} ({after_mi}Mi) is below the {MIN_LIMIT_MI}Mi floor"
            )
        if before_mi and after_mi and after_mi < before_mi * 0.5:
            risky = True
            reasons.append(
                f"memory limit dropped more than 50% ({before_limit} → {after_limit})"
            )
        if req_mi is not None and req_mi < MIN_REQUEST_MI:
            risky = True
            reasons.append(
                f"memory request {after_req} ({req_mi}Mi) is below the {MIN_REQUEST_MI}Mi floor"
            )
        if not risky:
            continue
        line = yaml_line_of(ch.after, "memory:", after_limit) or yaml_line_of(
            ch.after, "memory:"
        )
        evidence = [
            Evidence("file", ch.path, f"L{line or '?'}", snippet_at(ch.after, line)),
            Evidence("diff", ch.path, "unified diff", ch.unified_diff.strip()[:800]),
        ]
        restore = before_limit or "1Gi"
        restore_req = yaml_get(ch.before, "resources.requests.memory") or "512Mi"
        out.append(
            Finding(
                id="REL-MEM-001",
                title="Memory limit cut risks OOMKills",
                severity="high",
                category="reliability",
                summary="; ".join(reasons) + ". Checkout will be OOMKilled under peak load.",
                files=[ch.path],
                evidence=evidence,
                remediation=(
                    f"Restore requests.memory={restore_req} and limits.memory={restore}. "
                    "Right-size from observed usage, not a guess."
                ),
                patch=_memory_patch(ch, restore_req, restore),
            )
        )
    return out


def _public_lb(changes: list[FileChange]) -> list[Finding]:
    out: list[Finding] = []
    for ch in changes:
        hits: list[tuple[str, int | None, str]] = []
        if _is_yaml(ch.path):
            svc = yaml_get(ch.after, "service.type")
            if svc == "LoadBalancer":
                line = yaml_line_of(ch.after, "type:", "LoadBalancer")
                hits.append(("service.type=LoadBalancer", line, ch.after))
            scheme = (
                yaml_get(ch.after, "service.annotations.service.beta.kubernetes.io/aws-load-balancer-scheme")
                or _line_value(ch.after, "aws-load-balancer-scheme")
                or _line_value(ch.after, "alb.ingress.kubernetes.io/scheme")
            )
            if scheme == "internet-facing":
                line = yaml_line_of(ch.after, "internet-facing")
                hits.append(("scheme=internet-facing", line, ch.after))
        if ch.path.endswith(".tf"):
            assigns = hcl_string_assigns(ch.after)
            if assigns.get("internal") == "false" or assigns.get("scheme") == "internet-facing":
                line = yaml_line_of(ch.after, "internal") or yaml_line_of(ch.after, "scheme")
                hits.append(("public load balancer in Terraform", line, ch.after))
            if "0.0.0.0/0" in ch.after and "aws_security_group" in ch.after:
                line = yaml_line_of(ch.after, "0.0.0.0/0")
                hits.append(("security group open to the world", line, ch.after))
        if not hits:
            continue
        evidence = [
            Evidence("file", ch.path, f"L{line or '?'}", snippet_at(text, line))
            for _, line, text in hits
        ]
        evidence.append(Evidence("diff", ch.path, "unified diff", ch.unified_diff.strip()[:800]))
        out.append(
            Finding(
                id="SEC-LB-002",
                title="Public load balancer exposes the service",
                severity="critical",
                category="security",
                summary=(
                    "This change publishes checkout on the public internet "
                    f"({'; '.join(h[0] for h in hits)}). Payments traffic should stay on a "
                    "ClusterIP + internal ingress."
                ),
                files=[ch.path],
                evidence=evidence,
                remediation=(
                    "Use service.type=ClusterIP and an internal scheme. Put public entry only "
                    "on the edge ingress with WAF, never on the workload Service."
                ),
                patch=_lb_patch(ch),
            )
        )
    return out


def _iam(changes: list[FileChange]) -> list[Finding]:
    out: list[Finding] = []
    for ch in changes:
        if not ch.path.endswith(".tf"):
            continue
        parsed = iam_actions_and_resources(ch.after)
        wild_actions = [a for a in parsed["actions"] if is_wildcard(a)]
        wild_res = [r for r in parsed["resources"] if is_wildcard(r)]
        if not wild_actions and not wild_res:
            continue
        line = (
            yaml_line_of(ch.after, "s3:*")
            or yaml_line_of(ch.after, "iam:*")
            or yaml_line_of(ch.after, 'Resource = "*"')
            or yaml_line_of(ch.after, "Action")
        )
        before = iam_actions_and_resources(ch.before)
        evidence = [
            Evidence("file", ch.path, f"L{line or '?'}", snippet_at(ch.after, line)),
            Evidence("diff", ch.path, "unified diff", ch.unified_diff.strip()[:800]),
        ]
        out.append(
            Finding(
                id="SEC-IAM-003",
                title="IAM policy grants wildcard permissions",
                severity="critical",
                category="security",
                summary=(
                    f"IAM actions {wild_actions or parsed['actions']} on resources "
                    f"{wild_res or parsed['resources']} — far beyond least privilege. "
                    "A compromised checkout pod could mutate IAM or any S3 bucket."
                ),
                files=[ch.path],
                evidence=evidence,
                remediation=(
                    "Scope Action to the verbs the app needs (e.g. s3:GetObject) and "
                    "Resource to the receipts bucket ARN."
                ),
                patch=_iam_patch(ch, before) if before["actions"] else _iam_patch(ch, None),
            )
        )
    return out


def _is_yaml(path: str) -> bool:
    return path.endswith((".yaml", ".yml"))


def _line_value(text: str, key: str) -> str | None:
    for line in text.splitlines():
        if key in line and ":" in line:
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    return None


def _memory_patch(ch: FileChange, req: str, limit: str) -> str:
    lines = ch.after.splitlines(keepends=True)
    out_lines = []
    in_resources = False
    in_requests = False
    in_limits = False
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if stripped.startswith("resources:"):
            in_resources = True
        elif in_resources and indent == 0 and stripped and not stripped.startswith("#"):
            in_resources = in_requests = in_limits = False
        if in_resources and stripped.startswith("requests:"):
            in_requests, in_limits = True, False
        if in_resources and stripped.startswith("limits:"):
            in_limits, in_requests = True, False
        if in_requests and stripped.startswith("memory:"):
            pad = line[: len(line) - len(line.lstrip(" "))]
            out_lines.append(f"{pad}memory: {req}\n" if line.endswith("\n") else f"{pad}memory: {req}")
            continue
        if in_limits and stripped.startswith("memory:"):
            pad = line[: len(line) - len(line.lstrip(" "))]
            out_lines.append(f"{pad}memory: {limit}\n" if line.endswith("\n") else f"{pad}memory: {limit}")
            continue
        out_lines.append(line)
    return "".join(out_lines)


def _lb_patch(ch: FileChange) -> str:
    if ch.path.endswith(".tf"):
        text = ch.after.replace('internal = false', "internal = true")
        text = text.replace('scheme     = "internet-facing"', 'scheme     = "internal"')
        text = text.replace('scheme = "internet-facing"', 'scheme = "internal"')
        return text
    lines = []
    for line in ch.after.splitlines(keepends=True):
        if "type: LoadBalancer" in line:
            lines.append(line.replace("LoadBalancer", "ClusterIP"))
            continue
        if "internet-facing" in line:
            lines.append(line.replace("internet-facing", "internal"))
            continue
        lines.append(line)
    return "".join(lines)


def _iam_patch(ch: FileChange, before: dict | None) -> str:
    if ch.before.strip():
        return ch.before
    actions = '["s3:GetObject"]'
    resource = '"arn:aws:s3:::checkout-receipts/*"'
    if before and before.get("actions"):
        actions = "[" + ", ".join(f'"{a}"' for a in before["actions"]) + "]"
        if before.get("resources"):
            resource = "[" + ", ".join(f'"{r}"' for r in before["resources"]) + "]"
    text = ch.after
    text = _replace_block(text, "Action", actions)
    text = _replace_block(text, "Resource", resource)
    return text


def _replace_block(text: str, key: str, replacement: str) -> str:
    import re

    return re.sub(
        rf"{key}\s*=\s*(\[[^\]]*\]|\"[^\"]+\")",
        f"{key}   = {replacement}",
        text,
        count=1,
        flags=re.DOTALL,
    )
