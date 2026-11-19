variable "environment_name" {
  type        = string
  description = "Unique tenant ephemeral environment identifier (e.g., pr-102)"
}

variable "owner" {
  type        = string
  description = "Developer or team owning the ephemeral environment"
}

variable "cpu_limit" {
  type        = string
  default     = "2"
  description = "Hard CPU core limit for the ephemeral namespace"
}

variable "memory_limit" {
  type        = string
  default     = "4Gi"
  description = "Hard Memory limit for the ephemeral namespace"
}
