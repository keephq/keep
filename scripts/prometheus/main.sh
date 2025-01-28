#!/bin/bash

# Exit on any error
set -e

# Check if the cluster exists and handle cluster creation/deletion
if kind get clusters | grep -q "monitoring"; then
    read -p "Cluster 'monitoring' already exists. Do you want to delete it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting existing cluster..."
        kind delete clusters monitoring
        echo "Creating new cluster..."
        cat <<EOF | kind create cluster --name monitoring --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30900
    hostPort: 30900
    protocol: TCP
EOF
    else
        echo "Using existing cluster"
    fi
else
    echo "Creating new cluster..."
    cat <<EOF | kind create cluster --name monitoring --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30900
    hostPort: 30900
    protocol: TCP
EOF
fi

# Wait for cluster to be ready
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=ready node/monitoring-control-plane --timeout=60s

# Create namespace
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# Create service account and cluster role binding for API access
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus
rules:
- apiGroups: [""]
  resources:
  - nodes
  - nodes/proxy
  - nodes/metrics
  - services
  - endpoints
  - pods
  verbs: ["get", "list", "watch"]
- apiGroups: ["extensions", "networking.k8s.io"]
  resources:
  - ingresses
  verbs: ["get", "list", "watch"]
# Add these new permissions
- nonResourceURLs:
  - /metrics
  - /metrics/cadvisor
  - /metrics/resource
  verbs: ["get"]
- apiGroups: [""]
  resources:
  - services/proxy
  - endpoints/proxy
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus
subjects:
- kind: ServiceAccount
  name: prometheus
  namespace: monitoring
EOF

# Create ConfigMap for Prometheus config
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    rule_files:
      - /etc/prometheus/rules.yml
    scrape_configs:
      - job_name: 'kubernetes-apiservers'
        kubernetes_sd_configs:
        - role: endpoints
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
          insecure_skip_verify: true
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        relabel_configs:
        - source_labels: [__meta_kubernetes_namespace, __meta_kubernetes_service_name, __meta_kubernetes_endpoint_port_name]
          action: keep
          regex: default;kubernetes;https
      - job_name: 'kubernetes-nodes'
        kubernetes_sd_configs:
        - role: node
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
          insecure_skip_verify: true
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
        - role: pod
        relabel_configs:
        - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
          action: keep
          regex: true
        - source_labels: [__meta_kubernetes_pod_port_name]
          action: keep
          regex: metrics

      - job_name: 'cadvisor'
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
          insecure_skip_verify: true
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        kubernetes_sd_configs:
        - role: node
        relabel_configs:
        - target_label: __metrics_path__
          replacement: /metrics/cadvisor
        - action: labelmap
          regex: __meta_kubernetes_node_label_(.+)
        - target_label: instance
          replacement: kubernetes
      # Add kubelet metrics
      - job_name: 'kubelet'
        kubernetes_sd_configs:
        - role: node
        scheme: https
        tls_config:
          ca_file: /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
          insecure_skip_verify: true
        bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
        relabel_configs:
        - action: labelmap
          regex: __meta_kubernetes_node_label_(.+)
        metric_relabel_configs:
        - action: replace
          source_labels: [node]
          target_label: instance

      # Add node-exporter
      - job_name: 'node-exporter'
        kubernetes_sd_configs:
        - role: endpoints
        relabel_configs:
        - source_labels: [__meta_kubernetes_endpoints_name]
          regex: node-exporter
          action: keep
  rules.yml: |
    groups:
    - name: node
      rules:
      - alert: HighContainerMemoryUsage
        expr: (container_memory_working_set_bytes{container!=""} / container_spec_memory_limit_bytes{container!=""} * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High memory usage on {{ $labels.instance }}
          description: Node memory usage is above 90% for 5 minutes
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance)(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 90
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High CPU usage on {{ $labels.instance }}
          description: CPU usage is above 90% for 5 minutes
EOF

# Create Prometheus deployment
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      serviceAccountName: prometheus
      containers:
      - name: prometheus
        image: prom/prometheus:v2.48.0
        args:
        - "--config.file=/etc/prometheus/prometheus.yml"
        - "--storage.tsdb.path=/prometheus"
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: prometheus-config
          mountPath: /etc/prometheus/prometheus.yml
          subPath: prometheus.yml
        - name: prometheus-rules
          mountPath: /etc/prometheus/rules.yml
          subPath: rules.yml
        - name: prometheus-storage
          mountPath: /prometheus
      volumes:
      - name: prometheus-config
        configMap:
          name: prometheus-config
          items:
            - key: prometheus.yml
              path: prometheus.yml
      - name: prometheus-rules
        configMap:
          name: prometheus-config
          items:
            - key: rules.yml
              path: rules.yml
      - name: prometheus-storage
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: monitoring
spec:
  type: NodePort
  ports:
  - port: 9090
    targetPort: 9090
    nodePort: 30900
  selector:
    app: prometheus
EOF

# Deploy node exporter
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: node-exporter
  template:
    metadata:
      labels:
        app: node-exporter
    spec:
      hostNetwork: true
      hostPID: true
      containers:
      - name: node-exporter
        image: prom/node-exporter:latest
        ports:
        - containerPort: 9100
          protocol: TCP
          name: metrics
        volumeMounts:
        - name: proc
          mountPath: /host/proc
          readOnly: true
        - name: sys
          mountPath: /host/sys
          readOnly: true
      volumes:
      - name: proc
        hostPath:
          path: /proc
      - name: sys
        hostPath:
          path: /sys
---
apiVersion: v1
kind: Service
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  ports:
  - port: 9100
    targetPort: 9100
    protocol: TCP
    name: metrics
  selector:
    app: node-exporter
EOF

# Create API token
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: api-token
  namespace: monitoring
  annotations:
    kubernetes.io/service-account.name: prometheus
type: kubernetes.io/service-account-token
EOF


# Wait for Prometheus pod to be ready
echo "Waiting for Prometheus pod to be ready..."
kubectl wait --for=condition=ready pod -l app=prometheus -n monitoring --timeout=300s

# Get API token and cluster info
echo "Retrieving API token and cluster info..."
API_TOKEN=$(kubectl get secret api-token -n monitoring -o jsonpath='{.data.token}' | base64 --decode)
CLUSTER_IP=$(kubectl get svc kubernetes -n default -o jsonpath='{.spec.clusterIP}')
API_PORT=$(kubectl get svc kubernetes -n default -o jsonpath='{.spec.ports[0].port}')

echo "API Token: $API_TOKEN"
echo "To access the Kubernetes API from your local machine:"
echo "kubectl proxy &"
echo "Then you can access the API at: http://localhost:8001/api/v1/"
echo ""
echo "Or use curl with:"
echo "curl -k -H \"Authorization: Bearer $API_TOKEN\" https://localhost:6443/api/v1/"

echo "Prometheus is available at http://localhost:30900"
echo "Some test alerts have been configured for high CPU and memory usage"
echo "You can use the API token above to interact with the Kubernetes API server"
