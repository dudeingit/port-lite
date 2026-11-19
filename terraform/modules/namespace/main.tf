resource "kubernetes_namespace" "tenant" {
  metadata {
    name = var.environment_name

    labels = {
      "app.kubernetes.io/platform" = "port-lite"
      "environment-type"           = "ephemeral"
      "owner"                      = var.owner
    }
  }
}

resource "kubernetes_resource_quota" "tenant_quota" {
  metadata {
    name      = "${var.environment_name}-quota"
    namespace = kubernetes_namespace.tenant.metadata[0].name
  }

  spec {
    hard = {
      "limits.cpu"    = var.cpu_limit
      "limits.memory" = var.memory_limit
      "pods"          = "15"
      "services"      = "8"
    }
  }
}
