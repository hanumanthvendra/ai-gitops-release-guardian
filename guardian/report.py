"""Render a review as GitHub-flavored markdown (the PR comment)."""
from __future__ import annotations

from .models import Review

SEV = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW"}


def to_markdown(review: Review) -> str:
    lines = [
        "# GitOps Release Guardian",
        "",
        f"**Verdict:** `{review.verdict}` · **Overall risk:** `{review.overall_risk}` · "
        f"**Narrator:** `{review.generator}`",
        "",
        "> Read-only review. This agent does not apply Terraform or sync Argo CD. "
        "A human approves; GitOps deploys.",
        "",
        "## What changed",
        "",
    ]
    for item in review.what_changed:
        lines.append(f"- {item}")
    lines += ["", "## Findings", ""]
    if not review.findings:
        lines.append("No security, reliability, or IAM risks matched the detector set.")
    for f in review.findings:
        lines += [
            f"### {f.id} — {f.title}",
            "",
            f"`{SEV[f.severity]}` · `{f.category}` · files: {', '.join(f'`{p}`' for p in f.files)}",
            "",
            f.summary,
            "",
            "**Evidence**",
            "",
        ]
        for e in f.evidence:
            lines.append(f"- `{e.kind}` `{e.source}` `{e.locator}`")
            lines.append("")
            lines.append("```")
            lines.append(e.snippet.rstrip())
            lines.append("```")
            lines.append("")
        lines += ["**Remediation**", "", f.remediation, ""]
    if review.ci_checks:
        lines += ["## CI checks attached", ""]
        for c in review.ci_checks:
            lines.append(f"- `{c['tool']}` ← `{c['file']}`")
        lines.append("")
    lines += ["## Narrative", "", review.narrative, ""]
    if review.suggested_patch.strip():
        lines += [
            "## Suggested patch (human review)",
            "",
            "```diff",
            review.suggested_patch.rstrip(),
            "```",
            "",
        ]
    return "\n".join(lines)
