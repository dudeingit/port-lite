terraform {
  required_version = ">= 1.5.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25.0"
    }
  }
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

module "ephemeral_env_demo" {
  source = "./modules/namespace"

  environment_name = var.environment_name
  owner            = var.owner
  cpu_limit        = var.cpu_limit
  memory_limit     = var.memory_limit
}
