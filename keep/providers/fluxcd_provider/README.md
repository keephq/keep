# FluxCD Provider for Keep

This provider allows Keep to integrate with [Flux CD](https://fluxcd.io/), a GitOps tool for Kubernetes.

## Features

- **Topology Integration**: Pull topology information from Flux CD resources to visualize your GitOps deployment structure
- **Alert Integration**: Get alerts from Flux CD resources when deployments fail or have issues
- **Resource Monitoring**: Monitor Flux CD resources for failures and track their status
- **GitOps Insights**: Gain insights into your GitOps workflow and deployment process

## Setting up Flux CD

### Installation

1. Spin up a Kubernetes cluster (e.g., using Docker Desktop, Minikube, or a cloud provider)
2. Install Flux CD on your cluster:

   ```bash
   # Install Flux CLI
   # For macOS/Linux
   brew install fluxcd/tap/flux

   # For Windows
   # Download from https://github.com/fluxcd/flux2/releases

   # Check prerequisites
   flux check --pre

   # Bootstrap Flux CD
   flux bootstrap github \
     --owner=<your-github-username> \
     --repository=<repository-name> \
     --path=clusters/my-cluster \
     --personal
   ```

3. Create a sample GitRepository and Kustomization:

   ```yaml
   # gitrepository.yaml
   apiVersion: source.toolkit.fluxcd.io/v1
   kind: GitRepository
   metadata:
     name: podinfo
     namespace: flux-system
   spec:
     interval: 1m
     url: https://github.com/stefanprodan/podinfo
     ref:
       branch: master
   ```

   ```yaml
   # kustomization.yaml
   apiVersion: kustomize.toolkit.fluxcd.io/v1
   kind: Kustomization
   metadata:
     name: podinfo
     namespace: flux-system
   spec:
     interval: 5m
     path: "./kustomize"
     prune: true
     sourceRef:
       kind: GitRepository
       name: podinfo
   ```

   Apply these files:
   ```bash
   kubectl apply -f gitrepository.yaml
   kubectl apply -f kustomization.yaml
   ```

### Getting Access to Flux CD

1. For the Keep provider, you'll need access to the Kubernetes cluster where Flux CD is installed.
2. You can use one of the following authentication methods:

   a. **Kubeconfig file content** (recommended for external access):
      - Get your kubeconfig file content:
        ```bash
        cat ~/.kube/config
        ```
      - Use this content in the provider configuration

   b. **API server URL and token**:
      - Get the API server URL:
        ```bash
        kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
        ```
      - Create a service account and get a token:
        ```bash
        kubectl create serviceaccount flux-reader -n flux-system
        kubectl create clusterrolebinding flux-reader --clusterrole=view --serviceaccount=flux-system:flux-reader
        kubectl apply -f - <<EOF
        apiVersion: v1
        kind: Secret
        metadata:
          name: flux-reader-token
          namespace: flux-system
          annotations:
            kubernetes.io/service-account.name: flux-reader
        type: kubernetes.io/service-account-token
        EOF

        # Get the token
        kubectl get secret flux-reader-token -n flux-system -o jsonpath='{.data.token}' | base64 -d
        ```

   c. **In-cluster configuration** (when running Keep inside the Kubernetes cluster)

## Setting up the provider in Keep

1. Provider Name: Choose a name for your provider
2. Authentication: Use one of the methods described above
3. Namespace: The namespace where Flux CD is installed (default: flux-system)

## Usage in Workflows

You can use the FluxCD provider in your Keep workflows to retrieve Flux CD resources and create alerts for failed deployments:

```yaml
workflow:
  id: fluxcd-monitor
  name: "FluxCD Resource Monitor"
  description: "Monitor Flux CD resources and create alerts for failed deployments"
  triggers:
    - type: interval
      value: 1800  # 30 minutes in seconds

steps:
  - name: get-fluxcd-resources
    provider:
      type: fluxcd
      with:
        kubeconfig: "{{ env.KUBECONFIG }}"
        namespace: "flux-system"
    output: fluxcd_resources

  - name: check-resources
    run: |
      echo "Found {{ fluxcd_resources.kustomizations | length }} Kustomizations and {{ fluxcd_resources.helm_releases | length }} HelmReleases"

  - name: create-alerts-for-failed-kustomizations
    foreach: "{{ fluxcd_resources.kustomizations }}"
    if: '{{ item.status.conditions | selectattr("type", "equalto", "Ready") | selectattr("status", "equalto", "False") | list | length > 0 }}'
    alert:
      name: "Kustomization {{ item.metadata.name }} failed"
      description: "{{ item.status.conditions | selectattr('type', 'equalto', 'Ready') | map(attribute='message') | join(' ') }}"
      severity: high
      source: "fluxcd-kustomization"
```

See the [fluxcd_example.yml](../../examples/workflows/fluxcd_example.yml) file for a complete workflow example.

## Supported Resources

The provider can retrieve and monitor the following Flux CD resources:

- GitRepository
- HelmRepository
- HelmChart
- OCIRepository
- Bucket
- Kustomization
- HelmRelease

## Requirements

- Kubernetes cluster with Flux CD installed
- Kubernetes client version 24.2.0 or higher
- Access to the Kubernetes API server
