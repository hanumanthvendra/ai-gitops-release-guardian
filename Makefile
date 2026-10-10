.PHONY: help up demo demo-claude test safer mcp down
SHELL := /bin/bash
PY := python3

help:
	@echo "AI GitOps Release Guardian — evidence-based risk reviews"
	@echo ""
	@echo "  make up            no cluster required; sanity-check Python"
	@echo "  make demo          review the risky checkout PR (offline mock)"
	@echo "  make demo-claude   same review, Claude narrates (needs ANTHROPIC_API_KEY)"
	@echo "  make test          unit tests (no cluster, no API key)"
	@echo "  make safer         write the suggested files under out/safer and re-review"
	@echo "  make mcp           one-shot MCP tools/list + get_last_review over stdio"
	@echo "  make down          remove out/"

up:
	@$(PY) -c "import guardian,sys; print('guardian', guardian.__version__, sys.version.split()[0])"

demo:
	@chmod +x scripts/demo.sh
	@./scripts/demo.sh

demo-claude:
	@test -n "$$ANTHROPIC_API_KEY" || { echo "export ANTHROPIC_API_KEY first"; exit 1; }
	@$(PY) -m guardian review

test:
	@$(PY) -m unittest -q tests.test_guardian

safer:
	@$(PY) -m guardian safer-tree
	@$(PY) -m guardian review --proposed out/safer --ci out/no-ci --out out/after-patch

mcp:
	@$(PY) -m guardian review >/dev/null
	@printf '%s\n' \
	  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
	  '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
	  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_findings"}}' \
	  '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_gitops_context"}}' \
	  | $(PY) -m guardian.mcp_server

down:
	rm -rf out && echo "out/ removed."
