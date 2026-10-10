"""Ingest CI check artifacts (Trivy, Conftest) and attach them as evidence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Evidence, Finding

# Map scanner / policy IDs onto guardian finding IDs so one concern has
# both diff evidence and CI evidence.
ID_ALIASES = {
    "KSV011": "REL-MEM-001",
    "AVD-KSV-0011": "REL-MEM-001",
    "POL-MEM-FLOOR": "REL-MEM-001",
    "KSV-PUBLIC-SVC": "SEC-LB-002",
    "POL-LB-PUBLIC": "SEC-LB-002",
    "AVD-AWS-0057": "SEC-IAM-003",
    "POL-IAM-WILDCARD": "SEC-IAM-003",
}


def load_ci(ci_dir: Path | None) -> tuple[list[dict[str, Any]], dict[str, list[Evidence]]]:
    if ci_dir is None or not ci_dir.exists():
        return [], {}
    checks: list[dict[str, Any]] = []
    by_finding: dict[str, list[Evidence]] = {}
    for path in sorted(ci_dir.glob("*")):
        if path.suffix.lower() != ".json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.name.startswith("trivy"):
            checks.append({"tool": "trivy", "file": path.name, "raw": data})
            _ingest_trivy(data, by_finding)
        elif path.name.startswith("conftest") or path.name.startswith("policy"):
            checks.append({"tool": "conftest", "file": path.name, "raw": data})
            _ingest_conftest(data, by_finding)
        else:
            checks.append({"tool": path.stem, "file": path.name, "raw": data})
    return checks, by_finding


def attach_ci(findings: list[Finding], by_finding: dict[str, list[Evidence]]) -> None:
    for finding in findings:
        extra = by_finding.get(finding.id, [])
        if extra:
            finding.evidence.extend(extra)


def _ingest_trivy(data: Any, by_finding: dict[str, list[Evidence]]) -> None:
    results = data.get("Results", []) if isinstance(data, dict) else []
    for result in results:
        target = result.get("Target", "unknown")
        for mis in result.get("Misconfigurations") or []:
            rid = mis.get("ID") or mis.get("AVDID") or ""
            fid = ID_ALIASES.get(rid)
            if not fid:
                continue
            ev = Evidence(
                kind="ci",
                source=f"trivy:{target}",
                locator=rid,
                snippet=f"{mis.get('Severity', '')} {mis.get('Title', '')} — {mis.get('Message', mis.get('Description', ''))}".strip(),
            )
            by_finding.setdefault(fid, []).append(ev)


def _ingest_conftest(data: Any, by_finding: dict[str, list[Evidence]]) -> None:
    rows = data if isinstance(data, list) else data.get("results", [])
    for row in rows:
        filename = row.get("filename") or row.get("file") or "policy"
        for fail in row.get("failures") or row.get("Failed") or []:
            if isinstance(fail, str):
                msg, pid = fail, ""
            else:
                msg = fail.get("msg") or fail.get("message") or ""
                meta = fail.get("metadata") or {}
                pid = str(meta.get("id") or fail.get("id") or "")
            fid = ID_ALIASES.get(pid)
            if not fid:
                # Fall back: keyword match so a demo fixture still attaches.
                low = msg.lower()
                if "memory" in low or "oom" in low:
                    fid = "REL-MEM-001"
                elif "load balancer" in low or "internet-facing" in low or "public" in low:
                    fid = "SEC-LB-002"
                elif "iam" in low or "wildcard" in low:
                    fid = "SEC-IAM-003"
            if not fid:
                continue
            by_finding.setdefault(fid, []).append(
                Evidence(kind="policy", source=f"conftest:{filename}", locator=pid or "policy", snippet=msg)
            )
