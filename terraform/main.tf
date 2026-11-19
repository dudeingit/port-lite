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

  environment_name = "preview-feature-x"
  owner            = "rajkamal"
  cpu_limit        = "2"
  memory_limit     = "4Gi"
}
