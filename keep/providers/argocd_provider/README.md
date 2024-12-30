# Instructions for ~~a quick~~ setup

## Setting up ArgoCD

### Installation

1. Spin up Docker Daemon
2. Wait for kubernetes to start
3. Run the commands below
    ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   ```
4. If you're on Mac/Linux
    ```bash
    brew install argocd
    ```
   If you're on windows:
   Download the executable from here https://github.com/argoproj/argo-cd/releases/latest

5. cd to the `argocd_provider` & run this command (This will create a dummy ApplicationSetwith application app-1 and app-2)
    ```bash
   kubectl apply -f applicationset.yaml 
   ```
6. Run this command to open configmap
   ```bash
    kubectl edit configmap argocd-cm -n argocd
   ```
7. add this in the configmap
    ```yaml
    data:
      accounts.admin: apiKey, login
    ```
   Finally, your configmap should look similar to this
   ```yaml
    # Please edit the object below. Lines beginning with a '#' will be ignored,
    # and an empty file will abort the edit. If an error occurs while saving this file will be
    # reopened with the relevant failures.
    #
    apiVersion: v1
   
   ################ This is the new part###########
    data:
      accounts.admin: apiKey, login
   ################################################
    kind: ConfigMap
    metadata:
      annotations:
        kubectl.kubernetes.io/last-applied-configuration: |
          {"apiVersion":"v1","kind":"ConfigMap","metadata":{"annotations":{},"labels":{"app.kubernetes.io/name":"argocd-cm","app.kubernetes.io/part-of":"argocd"},"name":"argocd-cm","namespace":"argocd"}}
      creationTimestamp: "2024-12-27T15:40:06Z"
      labels:
        app.kubernetes.io/name: argocd-cm
        app.kubernetes.io/part-of: argocd
      name: argocd-cm
      namespace: argocd
      resourceVersion: "807860"
      uid: e2d8722f-e3bc-4299-9bb6-669b2873acdd
   ```

8. Restart your server
    ``` bash
   kubectl rollout restart deployment argocd-server -n argocd
   ```
   
9. Expose the port 
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8000:443 
   ```
   
10. Run this to get the initial Password & copy this
   ```bash
   argocd admin initial-password -n argocd 
   ```
11. Go to https://localhost:8000, login with credentials Username: admin, Password: <FROM_PREV_STEP>. 

12. Click `+ New App` > `Edit as YAML` > Paste the yaml below > Click `Save` > Click `Create`:
   ```yaml
    apiVersion: argoproj.io/v1alpha1
    kind: Application
    metadata:
      name: application-1
    spec:
      destination:
        name: ''
        namespace: default
        server: https://kubernetes.default.svc
      source:
        path: apps
        repoURL: https://github.com/argoproj/argocd-example-apps.git
        targetRevision: HEAD
      sources: []
      project: default
   ```

13. Find Card `application-1` and click `Sync` > Click `SYNCHRONIZE`.

### Getting Access Token

1. Go to `Settings` > `Accounts` > `Admin` > `Generate New` under tokens, this will generate an access token (Copy this).

### Setting up provider
1. Provider Name: UwU
2. Access Token: `<TOKEN_FROM_PREV_STEP>`
3. Deployment URL: `https://localhost:8000`