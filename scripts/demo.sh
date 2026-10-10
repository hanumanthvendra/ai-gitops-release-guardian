#!/usr/bin/env bash
# Recruiter-facing proofs: flag the risky PR, cite CI, suggest a patch, re-review.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -f api-key.txt ]; then
  export ANTHROPIC_API_KEY="$(tr -d '[:space:]' < api-key.txt)"
fi
PY=python3

hr(){ printf '\033[1;36m────────────────────────────────────────────────────────────\033[0m\n'; }
title(){ hr; printf '\033[1m  %s\033[0m\n' "$*"; hr; }

title "PROOF 1 — Risky PR: memory cut + public LB + IAM wildcard"
$PY -m guardian review --out out

title "PROOF 2 — Suggested patch applied to a copy (not to a cluster)"
$PY -m guardian safer-tree --out out/safer
echo
echo "Re-review of the patched tree (CI fixtures are for the original PR, so skip them):"
$PY -m guardian review --proposed out/safer --ci /nonexistent --out out/after-patch

title "PROOF 3 — Read-only GitOps context (MCP tools, no sync)"
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_gitops_context"}}' \
  | $PY -m guardian.mcp_server | tail -n 1

hr
echo "→ Findings are detector + CI evidence. The LLM only narrates."
echo "→ Argo CD remains the deployer. Guardian never applies."
