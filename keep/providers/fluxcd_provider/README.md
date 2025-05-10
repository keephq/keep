# Flux CD Provider

The Flux CD provider integrates [Flux CD](https://fluxcd.io/) with Keep, allowing you to:

1. Pull topology data from Flux CD resources (GitRepositories, Kustomizations, HelmReleases)
2. Get alerts from Flux CD events and resource status
3. Provide insights into the GitOps deployment process

## Overview

Flux CD is a GitOps tool for Kubernetes that provides continuous delivery through automated deployment, monitoring, and management of applications. This provider allows you to integrate Flux CD with Keep to get a single pane of glass for monitoring your GitOps deployments.

## Configuration

The Flux CD provider supports multiple authentication methods:

1. Kubeconfig file content (recommended for external access)
2. API server URL and token
3. In-cluster configuration (when running inside a Kubernetes cluster)
4. Default kubeconfig file (from ~/.kube/config)

### Authentication Options

| Option | Description | Required | Default |
|--------|-------------|----------|---------|
| kubeconfig | Kubeconfig file content | No | "" |
| context | Kubernetes context to use | No | "" |
| namespace | Namespace where Flux CD is installed | No | "flux-system" |
| api_server | Kubernetes API server URL | No | None |
| token | Kubernetes API token | No | "" |
| insecure | Skip TLS verification | No | false |

## Features

### Topology

The Flux CD provider pulls topology data from the following Flux CD resources:

- GitRepositories
- HelmRepositories
- HelmCharts
- OCI Repositories
- Buckets
- Kustomizations
- HelmReleases

The topology shows the relationships between these resources, allowing you to visualize the GitOps deployment process. Resources are categorized as:

- **Source**: GitRepositories, HelmRepositories, OCI Repositories, Buckets
- **Deployment**: Kustomizations, HelmReleases

### Alerts

The Flux CD provider gets alerts from two sources:

1. Kubernetes events related to Flux CD controllers
2. Status conditions of Flux CD resources (GitRepositories, Kustomizations, HelmReleases)

Alerts include:

- Failed GitRepository operations
- Failed Kustomization operations
- Failed HelmRelease operations
- Non-ready resources

Alert severity is determined based on:
- **Critical**: Events with "failed", "error", "timeout", "backoff", or "crash" in the reason
- **High**: Other warning events
- **Info**: Normal events

## Usage

1. Install the Flux CD provider in Keep
2. Configure the provider with your Kubernetes cluster information
3. View alerts and topology information in Keep

## Example Configurations

### Using Kubeconfig

```yaml
apiVersion: keep.sh/v1
kind: Provider
metadata:
  name: flux-cd
spec:
  type: fluxcd
  authentication:
    kubeconfig: |
      apiVersion: v1
      kind: Config
      clusters:
      - name: my-cluster
        cluster:
          server: https://kubernetes.example.com
          certificate-authority-data: BASE64_ENCODED_CA_CERT
      users:
      - name: my-user
        user:
          token: MY_TOKEN
      contexts:
      - name: my-context
        context:
          cluster: my-cluster
          user: my-user
      current-context: my-context
    context: my-context
    namespace: flux-system
```

### Using API Server and Token

```yaml
apiVersion: keep.sh/v1
kind: Provider
metadata:
  name: flux-cd
spec:
  type: fluxcd
  authentication:
    api_server: https://kubernetes.example.com
    token: MY_TOKEN
    namespace: flux-system
```

### Using In-Cluster Configuration

```yaml
apiVersion: keep.sh/v1
kind: Provider
metadata:
  name: flux-cd
spec:
  type: fluxcd
  authentication:
    namespace: flux-system
```

## Related Resources

- [Flux CD Documentation](https://fluxcd.io/docs/)
- [Flux CD GitHub Repository](https://github.com/fluxcd/flux2)
- [Keep Documentation](https://docs.keephq.dev)
