"""CLI: review a proposed GitOps change. Never mutates a cluster."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import review_trees
from .report import to_markdown
from .tree import apply_contents, compare
from .patch import suggested_files

ROOT = Path(__file__).resolve().parents[1]
DEMO_BASE = ROOT / "demo" / "baseline"
DEMO_PROP = ROOT / "demo" / "proposed"
DEMO_CI = ROOT / "demo" / "ci-results"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="guardian", description="Evidence-based GitOps change review")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("review", help="Review proposed vs baseline")
    r.add_argument("--baseline", type=Path, default=DEMO_BASE)
    r.add_argument("--proposed", type=Path, default=DEMO_PROP)
    r.add_argument("--ci", type=Path, default=DEMO_CI)
    r.add_argument("--out", type=Path, default=ROOT / "out")
    r.add_argument("--fail-on", choices=["off", "high", "critical"], default="off")
    r.add_argument("--json", action="store_true")

    s = sub.add_parser("safer-tree", help="Write suggested files under --out (still not applied)")
    s.add_argument("--baseline", type=Path, default=DEMO_BASE)
    s.add_argument("--proposed", type=Path, default=DEMO_PROP)
    s.add_argument("--out", type=Path, default=ROOT / "out" / "safer")

    args = p.parse_args(argv)
    if args.cmd == "review":
        return _review(args)
    if args.cmd == "safer-tree":
        return _safer(args)
    return 2


def _review(args) -> int:
    ci = args.ci if args.ci.exists() else None
    review = review_trees(args.baseline, args.proposed, ci)
    args.out.mkdir(parents=True, exist_ok=True)
    md = to_markdown(review)
    (args.out / "review.md").write_text(md, encoding="utf-8")
    (args.out / "review.json").write_text(json.dumps(review.to_dict(), indent=2), encoding="utf-8")
    (args.out / "suggested.patch").write_text(review.suggested_patch, encoding="utf-8")
    if args.json:
        print(json.dumps(review.to_dict(), indent=2))
    else:
        print(md)
    if args.fail_on == "critical" and review.overall_risk == "critical":
        return 2
    if args.fail_on == "high" and review.overall_risk in ("high", "critical"):
        return 2
    return 0


def _safer(args) -> int:
    import shutil

    from .detectors import detect

    if args.out.exists():
        shutil.rmtree(args.out)
    shutil.copytree(args.proposed, args.out, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    changes = compare(args.baseline, args.proposed)
    findings = detect(changes)
    files = suggested_files(changes, findings)
    apply_contents(args.out, files)
    print(f"Wrote safer overlay under {args.out} ({len(files)} patched files, not applied to any cluster).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
