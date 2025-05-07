# Instructions for setting up Flux CD Provider

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
