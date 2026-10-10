"""Read-only MCP-style stdio server for review + GitOps *context*.

This is not a chat UI and it cannot sync Argo CD. Tools only read the last
guardian report and a checked-in status fixture — the same contract a later
Argo CD MCP client would use for deployment context.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "out" / "review.json"
ARGO = ROOT / "gitops" / "status.json"

TOOLS = [
    {
        "name": "get_last_review",
        "description": "Return the latest guardian review (verdict, findings, evidence).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_findings",
        "description": "List finding ids, severity, files, and evidence locators.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_suggested_patch",
        "description": "Return the suggested unified diff. Does not apply it.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_gitops_context",
        "description": "Read-only Argo CD application status fixture (never syncs).",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _load_review() -> dict:
    if not REVIEW.exists():
        return {"error": "no review yet — run: python -m guardian review"}
    return json.loads(REVIEW.read_text(encoding="utf-8"))


def call_tool(name: str) -> dict:
    if name == "get_last_review":
        return _load_review()
    if name == "list_findings":
        review = _load_review()
        if "error" in review:
            return review
        rows = []
        for f in review.get("findings", []):
            rows.append(
                {
                    "id": f["id"],
                    "severity": f["severity"],
                    "title": f["title"],
                    "files": f["files"],
                    "evidence": [
                        f"{e['kind']}:{e['source']}:{e['locator']}" for e in f.get("evidence", [])
                    ],
                }
            )
        return {"findings": rows}
    if name == "get_suggested_patch":
        patch = ROOT / "out" / "suggested.patch"
        return {"patch": patch.read_text(encoding="utf-8") if patch.exists() else "", "applied": False}
    if name == "get_gitops_context":
        if ARGO.exists():
            return json.loads(ARGO.read_text(encoding="utf-8"))
        return {"error": "missing gitops/status.json"}
    return {"error": f"unknown tool {name}"}


def _respond(msg_id, result=None, error=None) -> None:
    body: dict = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        body["error"] = error
    else:
        body["result"] = result
    sys.stdout.write(json.dumps(body) + "\n")
    sys.stdout.flush()


def serve() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        method = req.get("method")
        msg_id = req.get("id")
        if method == "initialize":
            _respond(
                msg_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "gitops-release-guardian", "version": "0.1.0"},
                },
            )
        elif method == "tools/list":
            _respond(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            name = (req.get("params") or {}).get("name")
            data = call_tool(name)
            _respond(
                msg_id,
                {"content": [{"type": "text", "text": json.dumps(data, indent=2)}], "isError": "error" in data},
            )
        elif method in ("notifications/initialized", "initialized"):
            continue
        else:
            if msg_id is not None:
                _respond(msg_id, error={"code": -32601, "message": method})


if __name__ == "__main__":
    serve()
