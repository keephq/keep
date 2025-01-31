---
title: "Architecture"
sidebarTitle: "Architecture"
---


## High Level Architecture
Keep architecture composes of two main components:

1. **Keep API** - A FastAPI-based backend server that handles business logic and API endpoints.
2. **Keep Frontend** -  A Next.js-based frontend interface for user interaction.
3. **Websocket Server** - A Soketi server for real-time updates without page refreshes.
4. **Database Server** - A database used to store and manage persistent data. Supported databases include SQLite, PostgreSQL, MySQL, and SQL Server.

## Kubernetes Architecture

Keep uses a single unified NGINX ingress controller to route traffic to all components (frontend, backend, and websocket). The ingress handles path-based routing:

By default:
- `/` routed to **Frontend** (configurable via `global.ingress.frontendPrefix`)
- `/v2` routed to **Backend** (configurable via `global.ingress.backendPrefix`)
- `/websocket` routed to **WebSocket** (configurable via `global.ingress.websocketPrefix`)

### General Components

<Tip>Keep uses kubernetes secret manager to store secrets such as integrations credentials.</Tip>

| Kubernetes Resource | Purpose | Required/Optional | Source |
|:-------------------:|:-------:|:-----------------:|:------:|
| ServiceAccount | Provides an identity for processes that run in a Pod. Used mainly for Keep API to access kubernetes secret manager | Required | [serviceaccount.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/serviceaccount.yaml) |
| Role | Defines permissions for the ServiceAccount to manage secrets | Required | [role-secret-manager.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/role-secret-manager.yaml) |
| RoleBinding | Associates the Role with the ServiceAccount | Required | [role-binding-secret-manager.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/role-binding-secret-manager.yaml) |
| Secret Deletion Job | Cleans up Keep-related secrets when the Helm release is deleted | Required | [delete-secret-job.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/delete-secret-job.yaml) |

### Ingress Component
| Kubernetes Resource | Purpose | Required/Optional | Source |
|:-------------------:|:-------:|:-----------------:|:------:|
| Shared NGINX Ingress | Routes all external traffic via one entry point | Optional | [nginx-ingress.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/nginx-ingress.yaml) |

### Frontend Components

| Kubernetes Resource | Purpose | Required/Optional | Source |
|:-------------------:|:-------:|:-----------------:|:------:|
| Frontend Deployment | Manages the frontend application containers | Required | [frontend.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/frontend.yaml) |
| Frontend Service | Exposes the frontend deployment within the cluster | Required | [frontend-service.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/frontend-service.yaml) |
| Frontend Route (OpenShift) | Exposes the frontend service to external traffic on OpenShift | Optional | [frontend-route.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/frontend-route.yaml) |
| Frontend HorizontalPodAutoscaler | Automatically scales the number of frontend pods | Optional | [frontend-hpa.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/frontend-hpa.yaml) |

#### Backend Components

| Kubernetes Resource | Purpose | Required/Optional | Source |
|:-------------------:|:-------:|:-----------------:|:------:|
| Backend Deployment | Manages the backend application containers | Required (if backend enabled) | [backend.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/backend.yaml) |
| Backend Service | Exposes the backend deployment within the cluster | Required (if backend enabled) | [backend-service.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/backend-service.yaml) |
| Backend Route (OpenShift) | Exposes the backend service to external traffic on OpenShift | Optional | [backend-route.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/backend-route.yaml) |
| Backend HorizontalPodAutoscaler | Automatically scales the number of backend pods | Optional | [backend-hpa.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/backend-hpa.yaml) |

#### Database Components
<Tip>Database components are optional. You can spin up Keep with your own database.</Tip>

| Kubernetes Resource | Purpose | Required/Optional | Source |
|:-------------------:|:-------:|:-----------------:|:------:|
| Database Deployment | Manages the database containers (e.g. MySQL or Postgres) | Optional | [db.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/db.yaml) |
| Database Service | Exposes the database deployment within the cluster | Required (if deployment enabled) | [db-service.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/db-service.yaml) |
| Database PersistentVolume | Provides persistent storage for the database | Optional | [db-pv.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/db-pv.yaml) |
| Database PersistentVolumeClaim | Claims the persistent storage for the database | Optional | [db-pvc.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/db-pvc.yaml) |

#### WebSocket Components
<Tip>WebSocket components are optional. You can spin up Keep with your own *Pusher compatible* WebSocket server.</Tip>

| Kubernetes Resource | Purpose | Required/Optional | Source |
|:-------------------:|:-------:|:-----------------:|:------:|
| WebSocket Deployment | Manages the WebSocket server containers (Soketi) | Optional | [websocket-server.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/websocket-server.yaml) |
| WebSocket Service | Exposes the WebSocket deployment within the cluster | Required (if WebSocket enabled) | [websocket-server-service.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/websocket-server-service.yaml) |
| WebSocket Route (OpenShift) | Exposes the WebSocket service to external traffic on OpenShift | Optional | [websocket-server-route.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/websocket-server-route.yaml) |
| WebSocket HorizontalPodAutoscaler | Automatically scales the number of WebSocket server pods | Optional | [websocket-server-hpa.yaml](https://github.com/keephq/helm-charts/blob/main/charts/keep/templates/websocket-server-hpa.yaml) |

These tables provide a comprehensive overview of the Kubernetes resources used in the Keep architecture, organized by component type. Each table describes the purpose of each resource, indicates whether it's required or optional, and provides a direct link to the source template in the Keep Helm charts GitHub repository.

### Kubernetes Configuration
<Tip>This sections covers only kubernetes-specific configuration. To learn about Keep-specific configuration, controlled by environment variables, see [Keep Configuration](/deployment/configuration)</Tip>

Each of these components can be customized via the `values.yaml` file in the Helm chart.


Below are key configurations that can be adjusted for each component.

#### 1. Frontend Configuration
```yaml
frontend:
  enabled: true                 # Enable or disable the frontend deployment.
  replicaCount: 1               # Number of frontend replicas.
  image:
    repository: us-central1-docker.pkg.dev/keephq/keep/keep-ui
    pullPolicy: Always          # Image pull policy (Always, IfNotPresent).
    tag: latest
  serviceAccount:
    create: true                # Create a new service account.
    name: ""                    # Service account name (empty for default).
  podAnnotations: {}            # Annotations for frontend pods.
  podSecurityContext: {}        # Security context for the frontend pods.
  securityContext: {}           # Security context for the containers.
  service:
    type: ClusterIP              # Service type (ClusterIP, NodePort, LoadBalancer).
    port: 3000                  # Port on which the frontend service is exposed.
```

#### 2. Backend Configuration
```yaml
backend:
  enabled: true                # Enable or disable the backend deployment.
  replicaCount: 1              # Number of backend replicas.
  image:
    repository: us-central1-docker.pkg.dev/keephq/keep/keep-api
    pullPolicy: Always         # Image pull policy (Always, IfNotPresent).
  serviceAccount:
    create: true               # Create a new service account.
    name: ""                   # Service account name (empty for default).
  podAnnotations: {}           # Annotations for backend pods.
  podSecurityContext: {}       # Security context for backend pods.
  securityContext: {}          # Security context for containers.
  service:
    type: ClusterIP      # Service type (ClusterIP, NodePort, LoadBalancer).
    port: 8080           # Port on which the backend API is exposed.
```

#### 3. WebSocket Server Configuration
Keep uses Soketi as its websocket server. To learn how to configure it, please see [Soketi docs](https://github.com/soketi/charts/tree/master/charts/soketi).


#### 4. Database Configuration
Keep supports plenty of database (e.g. postgresql, mysql, sqlite, etc). It is out of scope to describe here how to deploy all of them to k8s. If you have specific questions - [contact us](https://slack.keephq.dev) and we will be happy to help.
