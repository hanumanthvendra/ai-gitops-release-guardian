"""Assemble a review: diff → detectors → CI evidence → patch → narration."""
from __future__ import annotations

from pathlib import Path

from .ci import attach_ci, load_ci
from .detectors import detect
from .explain import backend, narrate
from .models import Review
from .patch import suggested_unified_diff
from .tree import compare

RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def review_trees(baseline: Path, proposed: Path, ci_dir: Path | None = None) -> Review:
    changes = compare(baseline, proposed)
    findings = detect(changes)
    checks, ci_ev = load_ci(ci_dir)
    attach_ci(findings, ci_ev)

    what = [
        f"{ch.status} `{ch.path}` ({len(ch.unified_diff.splitlines())} diff lines)"
        for ch in changes
    ]
    if not what:
        what = ["No Terraform / Helm / Kubernetes text files changed."]

    overall = "low"
    for f in findings:
        if RANK[f.severity] > RANK[overall]:
            overall = f.severity
    if overall in ("critical", "high"):
        verdict = "block"
    elif overall == "medium":
        verdict = "warn"
    else:
        verdict = "allow"

    patch = suggested_unified_diff(changes, findings)
    review = Review(
        verdict=verdict,
        overall_risk=overall,  # type: ignore[arg-type]
        what_changed=what,
        findings=findings,
        suggested_patch=patch,
        narrative="",
        generator=backend(),
        ci_checks=[{"tool": c["tool"], "file": c["file"]} for c in checks],
    )
    review.narrative = narrate(review)
    return review
