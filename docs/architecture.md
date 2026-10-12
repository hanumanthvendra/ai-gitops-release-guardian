# Architecture — AI GitOps Release Guardian

The guardian is a **read-only review stage** in an existing GitOps path. Jenkins still lint-scans-policy. Argo CD still deploys. The model never applies Terraform and never syncs an Application.

Motion diagram (open in a browser): https://hanumanthvendra.github.io/gitops-release-guardian/

## System context

```mermaid
flowchart LR
  Dev[Engineer] -->|opens PR| Git[Git: Helm + Terraform]
  Git --> Jenkins
  subgraph Jenkins["Jenkins CI"]
    Lint[helm lint / terraform fmt]
    Scan[Trivy config]
    Policy[Conftest / Rego]
    Guard[Guardian review]
    Lint --> Scan --> Policy --> Guard
  end
  Guard -->|review.md + suggested.patch| PR[PR comment]
  PR -->|human merge| Git
  Git -->|desired state| Argo[Argo CD]
  Argo -->|sync| Cluster[Kubernetes]
  Guard -.->|no apply / no app sync| Cluster
```

## Review pipeline (inside the guardian)

```mermaid
sequenceDiagram
  participant PR as Proposed tree
  participant Det as Detectors
  participant CI as Trivy + Conftest
  participant LLM as Narrator mock/Claude
  participant Out as review.md + patch

  PR->>Det: unified diff (baseline vs proposed)
  Det->>Det: REL-MEM-001 / SEC-LB-002 / SEC-IAM-003
  CI->>Det: attach evidence (KSV011, POL-*, AVD-AWS-0057)
  Det->>LLM: findings JSON only
  Note over LLM: Must not invent risks
  LLM->>Out: narrative
  Det->>Out: suggested unified diff
  Note over Out: Human reviews. Argo CD deploys.
```

## Control plane vs data plane

| Layer | Owns | Must not |
|---|---|---|
| Detectors + Rego + Trivy | Whether a finding exists | Talk to the cluster |
| LLM narrator | Wording of the report | Add findings, apply patches |
| Human + Jenkins `input` | Merge decision | Skip evidence |
| Argo CD | Reconcile Git → cluster | Be driven by the model |

Read-only MCP tools (`get_last_review`, `list_findings`, `get_suggested_patch`, `get_gitops_context`) expose the last report and a status fixture. There is no `sync` tool. Pair later with Argo CD MCP for live application status — keep mutations in Argo.
