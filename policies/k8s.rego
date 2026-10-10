package gitops.k8s

import future.keywords.if

# Memory floor — same number the guardian detector uses (256Mi).
deny[msg] if {
  input.resources.limits.memory
  endswith(input.resources.limits.memory, "Mi")
  mem := to_number(trim_suffix(input.resources.limits.memory, "Mi"))
  mem < 256
  msg := sprintf("POL-MEM-FLOOR: memory limit %s is below 256Mi", [input.resources.limits.memory])
}

deny[msg] if {
  input.service.type == "LoadBalancer"
  msg := "POL-LB-PUBLIC: app Services must stay ClusterIP; use the edge ingress for public entry"
}

deny[msg] if {
  scheme := input.service.annotations["service.beta.kubernetes.io/aws-load-balancer-scheme"]
  scheme == "internet-facing"
  msg := "POL-LB-PUBLIC: internet-facing load balancer is not allowed on this chart"
}
