package gitops.terraform

import future.keywords.if
import future.keywords.in

deny[msg] if {
  some stmt in input.Statement
  some action in stmt.Action
  action == "*"
  msg := "POL-IAM-WILDCARD: IAM Action '*' is not allowed"
}

deny[msg] if {
  some stmt in input.Statement
  some action in stmt.Action
  endswith(action, ":*")
  msg := sprintf("POL-IAM-WILDCARD: IAM Action %s is a service wildcard", [action])
}

deny[msg] if {
  some stmt in input.Statement
  stmt.Resource == "*"
  msg := "POL-IAM-WILDCARD: IAM Resource '*' is not allowed"
}
