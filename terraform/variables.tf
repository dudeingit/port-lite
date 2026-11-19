variable "environment_name" {
  description = "Name of the ephemeral preview environment and Kubernetes namespace"
  type        = string
}

variable "owner" {
  description = "Owner or creator of the preview environment"
  type        = string
  default     = "developer"
}

variable "cpu_limit" {
  description = "CPU resource quota limit for the namespace"
  type        = string
  default     = "2"
}

variable "memory_limit" {
  description = "Memory resource quota limit for the namespace"
  type        = string
  default     = "4Gi"
}
