# Keep Helm Chart
The Keep Helm Chart provides a convenient way to deploy and manage Keep on Kubernetes using Helm, a package manager for Kubernetes applications.

# Installation
The easiest way to install Keep with Helm is with the following command:
`helm install -f chart/keep/values.yaml keep chart/keep/`

# Uninstallation
`helm uninstall keep`

# Configuration
Keep's Helm Chart supports the following `values.yaml`:
- backend.image: the backend image (default: us-central1-docker.pkg.dev/keephq/keep/keep-api)
- frontend.image: the frontend image (default: us-central1-docker.pkg.dev/keephq/keep/keep-ui)
- frontend.publicApiUrl: the frontend will use this URL as a backend from your browser ("client components"). default: http://localhost:8080. for production environment this should be the backend DNS/external IP.
- frontend.internalApiUrl: the frontend will use this URL as a backend from the container ("server components") default: http://keep-backend:8080
  frontend.env: development

# Local Kubernetes
For local kubernetes without external IP (such as NodePort or LoadBalancer), you'll need to run port forwarding:

## Port forward
```bash
kubectl port-forward svc/keep-frontend 3000:3000 & \
kubectl port-forward svc/keep-websocket 6001:6001 &
```
