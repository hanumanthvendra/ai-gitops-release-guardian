"""Pluggable narration. Findings stay detector-owned; the LLM only writes prose.

No key  → deterministic mock (CI-safe).
ANTHROPIC_API_KEY → Claude, still forbidden from inventing findings.
"""
from __future__ import annotations

import json
import os

from .models import Review

SYSTEM = (
    "You are a staff platform engineer reviewing a GitOps pull request. "
    "Explain ONLY the findings JSON you are given. Cite each claim with its "
    "finding id and evidence locator (file:line or CI check id). "
    "Do not invent risks. Do not tell anyone to kubectl-apply or terraform-apply. "
    "Argo CD deploys after a human merges. Keep the report under 400 words."
)


def backend() -> str:
    return "claude" if os.environ.get("ANTHROPIC_API_KEY") else "mock"


def narrate(review: Review) -> str:
    if backend() == "claude":
        return _claude(review)
    return _mock(review)


def _mock(review: Review) -> str:
    lines = [
        f"Verdict: **{review.verdict.upper()}** — overall risk {review.overall_risk}.",
        "",
        "What changed:",
        *(f"- {item}" for item in review.what_changed),
        "",
        "What could go wrong (evidence-backed):",
    ]
    for f in review.findings:
        cites = ", ".join(f"{e.source} {e.locator}" for e in f.evidence[:3])
        lines.append(f"- **{f.id}** ({f.severity} {f.category}): {f.summary}")
        lines.append(f"  Evidence: {cites}")
        lines.append(f"  Safer path: {f.remediation}")
    lines += [
        "",
        "A suggested patch is attached for a human to review. The guardian does "
        "not apply changes. After approval, Argo CD syncs Git — not this agent.",
        "",
        "(mock narrator — set ANTHROPIC_API_KEY to phrase this with Claude. "
        "The findings, evidence, and patch are identical either way.)",
    ]
    return "\n".join(lines)


def _claude(review: Review) -> str:
    import anthropic

    payload = {
        "verdict": review.verdict,
        "overall_risk": review.overall_risk,
        "what_changed": review.what_changed,
        "findings": [
            {
                "id": f.id,
                "title": f.title,
                "severity": f.severity,
                "category": f.category,
                "summary": f.summary,
                "files": f.files,
                "evidence": [
                    {"kind": e.kind, "source": e.source, "locator": e.locator, "snippet": e.snippet[:400]}
                    for e in f.evidence
                ],
                "remediation": f.remediation,
            }
            for f in review.findings
        ],
    }
    try:
        resp = anthropic.Anthropic().messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=900,
            system=SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
        )
        return next((b.text for b in resp.content if b.type == "text"), "").strip()
    except Exception as exc:  # auth, rate limit, network — findings still stand
        return _mock(review) + f"\n\n[LLM error: {exc}. Findings and patch are unchanged.]"
