from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Severity = Literal["critical", "high", "medium", "low"]
Category = Literal["security", "reliability", "cost"]
EvidenceKind = Literal["diff", "file", "ci", "policy"]
Verdict = Literal["block", "warn", "allow"]


@dataclass(frozen=True)
class Evidence:
    kind: EvidenceKind
    source: str
    locator: str
    snippet: str


@dataclass
class Finding:
    id: str
    title: str
    severity: Severity
    category: Category
    summary: str
    files: list[str]
    evidence: list[Evidence]
    remediation: str
    patch: str | None = None


@dataclass
class FileChange:
    path: str
    status: str  # added | modified | deleted
    before: str
    after: str
    unified_diff: str


@dataclass
class Review:
    verdict: Verdict
    overall_risk: Severity
    what_changed: list[str]
    findings: list[Finding]
    suggested_patch: str
    narrative: str
    generator: str
    ci_checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
