# Port-Lite

A lightweight Internal Developer Platform (IDP) for provisioning and tearing down isolated, ephemeral Kubernetes preview environments on demand.

Built for local developer velocity on **WSL2 + Docker Desktop + `kind`**, **Port-Lite** pairs modular **Terraform** namespace/quota isolation with a parameterized **Helm** workload chart and a **Flask** orchestration API emitting structured JSON telemetry.

---

## Architecture Overview

```text
  [Client / Webhook / curl]
             │
             ▼
  ┌─────────────────────┐
  │   Flask API         │  (api/app.py + JSON telemetry)
  │  POST / DELETE      │
  └──────┬───────┬──────┘
         │       │
  1. tf  │       │ 2. helm upgrade --install / uninstall
         ▼       ▼
  ┌──────────────┐   ┌───────────────────────────────────┐
  │  Terraform   │   │  Kubernetes Cluster (kind/WSL2)   │
  │  Namespace & │──▶│  Namespace: preview-<env>         │
  │  Quotas      │   │  Workload & Service (app-template)│
  └──────────────┘   └───────────────────────────────────┘
````
Repository Structure:
```
port-lite/
├── .github/
│   └── workflows/
│       └── port-lite-ci.yml     # Terraform validate, Helm lint, API smoke test
├── api/
│   ├── app.py                   # Provision & teardown API + JSON logger
│   └── requirements.txt         # Flask, Gunicorn, Pydantic, python-json-logger
├── helm/
│   └── app-template/            # Reusable Helm chart for preview workloads
└── terraform/
    └── modules/
        └── namespace/           # Isolated namespace and resource quota module
````
API Reference
GET /health
Returns service liveness status and logs a structured health check event.

Response (200 OK):
{
  "status": "healthy",
  "service": "port-lite-api"
}
POST /api/v1/environments
Provisions an isolated Kubernetes namespace and resource quotas via Terraform, then installs or upgrades a Helm release (pr-<environment_name>).

Request Body:
{
  "environment_name": "preview-feature-x",
  "owner": "rajkamal"
}
Response (201 Created):
{
  "message": "Environment preview-feature-x successfully provisioned and deployed!",
  "namespace": "preview-feature-x",
  "release": "pr-preview-feature-x"
}
DELETE /api/v1/environments/<env_name>
Uninstalls the Helm release (pr-<env_name>) and destroys the Terraform-managed namespace and quota resources.

Response (200 OK):
{
  "message": "Environment preview-feature-x successfully torn down and purged!",
  "namespace": "preview-feature-x"
}

Local Setup (WSL2 + kind)
Prerequisites
Windows with WSL2 (Ubuntu) and Docker Desktop (WSL2 integration enabled)

kind, kubectl, helm, terraform, and python3 installed in WSL2

1. Start Cluster & Install Python Dependencies
   cd ~/port-lite
kind create cluster --name port-lite-cluster
pip install -r api/requirements.txt

2. Run the Orchestration API
   python3 api/app.py
3. Provision, Inspect, and Tear Down an Environment
   # Provision
curl -X POST http://localhost:5000/api/v1/environments \
  -H "Content-Type: application/json" \
  -d '{"environment_name": "preview-feature-x", "owner": "rajkamal"}'

# Inspect pods and services
kubectl get pods,svc -n preview-feature-x

# Tear down
curl -X DELETE http://localhost:5000/api/v1/environments/preview-feature-x
CI/CD & Observability

GitHub Actions (.github/workflows/port-lite-ci.yml): Runs terraform fmt -check, terraform init -backend=false, terraform validate, helm lint, helm template, and a Flask /health smoke test on pushes and pull requests.

Structured Telemetry: api/app.py uses python-json-logger to output JSON logs containing service, action, outcome, environment_name, and duration_ms.

---

### Save and Push `README.md`

```bash
cd ~/port-lite
cat <<'EOF' > README.md
# Port-Lite

A lightweight Internal Developer Platform (IDP) for provisioning and tearing down isolated, ephemeral Kubernetes preview environments on demand.

Built for local developer velocity on **WSL2 + Docker Desktop + `kind`**, **Port-Lite** pairs modular **Terraform** namespace/quota isolation with a parameterized **Helm** workload chart and a **Flask** orchestration API emitting structured JSON telemetry.

---

## Architecture Overview

```text
  [Client / Webhook / curl]
             │
             ▼
  ┌─────────────────────┐
  │   Flask API         │  (api/app.py + JSON telemetry)
  │  POST / DELETE      │
  └──────┬───────┬──────┘
         │       │
  1. tf  │       │ 2. helm upgrade --install / uninstall
         ▼       ▼
  ┌──────────────┐   ┌───────────────────────────────────┐
  │  Terraform   │   │  Kubernetes Cluster (kind/WSL2)   │
  │  Namespace & │──▶│  Namespace: preview-<env>         │
  │  Quotas      │   │  Workload & Service (app-template)│
  └──────────────┘   └───────────────────────────────────┘
```
Repository Structure
port-lite/
├── .github/
│   └── workflows/
│       └── port-lite-ci.yml     # Terraform validate, Helm lint, API smoke test
├── api/
│   ├── app.py                   # Provision & teardown API + JSON logger
│   └── requirements.txt         # Flask, Gunicorn, Pydantic, python-json-logger
├── helm/
│   └── app-template/            # Reusable Helm chart for preview workloads
└── terraform/
    └── modules/
        └── namespace/           # Isolated namespace and resource quota module



        
