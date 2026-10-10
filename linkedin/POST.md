# LinkedIn post — AI GitOps Release Guardian

Shipping an AI that can `kubectl apply` is a demo. Shipping one that **cannot**, and still changes how you review a PR, is the platform story.

I built a **GitOps Release Guardian** that sits in CI next to Helm lint, Terraform fmt, Trivy, and policy tests.

A pull request that:

- cuts a service memory limit (OOM risk)
- opens a public load balancer
- grants `s3:*` / `iam:*` on `*`

…gets a short report: **what changed**, **what could go wrong**, **which files and CI checks support each finding**, and a **suggested patch**.

The model only narrates. Detectors own the findings. A human merges. **Argo CD deploys.** The agent never syncs the cluster.

That’s the split I want in production AI + DevOps: intelligence on the review, control on the release.

`make test && make demo` — laptop, no cluster, no API key.

#GitOps #Kubernetes #Terraform #ArgoCD #Jenkins #PlatformEngineering #DevSecOps
