from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

from guardian.ci import attach_ci, load_ci
from guardian.detectors import detect
from guardian.engine import review_trees
from guardian.mcp_server import call_tool
from guardian.patch import suggested_files
from guardian.tree import apply_contents, compare

BASE = ROOT / "demo" / "baseline"
PROP = ROOT / "demo" / "proposed"
CI = ROOT / "demo" / "ci-results"


class TestDemoPR(unittest.TestCase):
    def setUp(self) -> None:
        self.changes = compare(BASE, PROP)
        self.findings = detect(self.changes)
        self.by_id = {f.id: f for f in self.findings}

    def test_flags_memory_public_lb_and_iam(self) -> None:
        self.assertIn("REL-MEM-001", self.by_id)
        self.assertIn("SEC-LB-002", self.by_id)
        self.assertIn("SEC-IAM-003", self.by_id)
        self.assertEqual(self.by_id["REL-MEM-001"].category, "reliability")
        self.assertEqual(self.by_id["SEC-LB-002"].severity, "critical")
        self.assertEqual(self.by_id["SEC-IAM-003"].severity, "critical")
        self.assertIn("s3:*", self.by_id["SEC-IAM-003"].summary)
        self.assertIn("iam:*", self.by_id["SEC-IAM-003"].summary)

    def test_evidence_points_at_changed_files(self) -> None:
        mem = self.by_id["REL-MEM-001"]
        self.assertTrue(any("values.yaml" in p for p in mem.files))
        self.assertTrue(any(e.kind in ("file", "diff") for e in mem.evidence))
        iam = self.by_id["SEC-IAM-003"]
        self.assertTrue(any(p.endswith("iam.tf") for p in iam.files))

    def test_ci_checks_attach_as_evidence(self) -> None:
        _, by_finding = load_ci(CI)
        attach_ci(self.findings, by_finding)
        for fid in ("REL-MEM-001", "SEC-LB-002", "SEC-IAM-003"):
            kinds = {e.kind for e in self.by_id[fid].evidence}
            self.assertTrue(kinds & {"ci", "policy"}, msg=f"{fid} missing CI/policy evidence: {kinds}")

    def test_suggested_patch_clears_high_findings(self) -> None:
        files = suggested_files(self.changes, self.findings)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            apply_contents(dest, files)
            leftover = detect(compare(BASE, dest))
            ids = {f.id for f in leftover}
            self.assertNotIn("REL-MEM-001", ids)
            self.assertNotIn("SEC-LB-002", ids)
            self.assertNotIn("SEC-IAM-003", ids)

    def test_review_blocks_and_does_not_invent_findings(self) -> None:
        review = review_trees(BASE, PROP, CI)
        self.assertEqual(review.verdict, "block")
        self.assertEqual(review.overall_risk, "critical")
        self.assertTrue(review.suggested_patch)
        self.assertIn("values.yaml", review.suggested_patch)
        self.assertIn("REL-MEM-001", review.narrative)
        self.assertNotIn("kubectl apply", review.narrative.lower())
        self.assertNotIn("terraform apply", review.narrative.lower())

    def test_identical_trees_allow(self) -> None:
        review = review_trees(BASE, BASE, None)
        self.assertEqual(review.findings, [])
        self.assertEqual(review.verdict, "allow")

    def test_guardian_sources_never_apply(self) -> None:
        forbidden = ("kubectl apply", "terraform apply", "argocd app sync", "helm upgrade")
        for path in (ROOT / "guardian").rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, text, msg=f"{path} mentions {phrase}")


class TestMcpReadOnly(unittest.TestCase):
    def test_unknown_tool(self) -> None:
        self.assertIn("error", call_tool("sync_application"))

    def test_gitops_context_does_not_sync(self) -> None:
        ctx = call_tool("get_gitops_context")
        self.assertEqual(ctx.get("autoSync"), False)
        self.assertNotIn("sync now", json.dumps(ctx).lower())


if __name__ == "__main__":
    unittest.main()
