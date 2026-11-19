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
Repository Structure
