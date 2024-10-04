# THIS DOCUMENT IS STILL UNDER CONSTRUCTION

## 1. Create a Kubernetes Cluster

```bash
# Set the project
gcloud config set project keep-dev-429814

# Get Kubernetes cluster credentials
gcloud container clusters get-credentials keep-stress --zone us-central1-c --project keep-dev-429814
```

## 2. Install Keep

### a. Add Helm Chart Repository

```bash
helm repo add keephq https://keephq.github.io/helm-charts
helm pull keephq/keep
```

### b. Create a Namespace for Keep

```bash
kubectl create namespace keep
```

### c. Install Keep via Helm

```bash
# Install from the repository
helm install keep keephq/keep --namespace keep

# Or install locally if charts are available locally
helm install keep ./charts/keep --namespace keep
```

### d. Verify Installation

```bash
kubectl -n keep describe pod keep-backend-697f6b946f-v2jxp
kubectl -n keep logs keep-frontend-577fdf5497-r8ht9
```

---

## 3. Import Alerts

(Instructions for importing alerts will go here.)

---

## 4. Uninstall Keep

```bash
helm uninstall keep --namespace keep
```

---

## 5. Database Operations

### a. Copy the Database

```bash
# Execute into the database pod
kubectl -n keep exec -it keep-database-86dd6b6775-92sz4 /bin/bash

# Copy the keep.sql file into the database pod
kubectl -n keep cp ./keep.sql keep-database-659c69689-vxhkz:/tmp/keep.sql

# Import the SQL file into the MySQL database
kubectl -n keep exec -it keep-database-659c69689-vxhkz -- bash -c "mysql -u root keep < /tmp/keep.sql"
```

### b. Exec into the Database Pod

```bash
kubectl -n keep exec -it keep-database-86dd6b6775-92sz4 -- /bin/bash
```

### c. Exec into Keep Backend Pod

```bash
kubectl -n keep exec -it keep-backend-64c4d7ddb7-7p5q5 /bin/bash
```

---

# No Load
## 500k alerts - 1Gi/250m cpu: get_last_alerts 2 minutes and 30 seconds
- Keep Backend Workers get timeout after a one minutes (500's for preset and alert endpoints)
## 500k alerts - 2Gi/500m cpu:
- default mysql: get_last_alerts 1 minutes and 30 seconds
- innodb_buffer_pool_size = 4294967296: 25 seconds, 3 seconds after cache
## 500k alerts - 4Gi/1 cpu: get_last_alerts 2 minutes and 30 seconds
-
## 500k alerts - 8Gi/1 cpu: get_last_alerts 2 minutes and 30 seconds

# Load 10 alerts per minute

# Load 100 alerts per minute

# Load 1000 alerts per minute


## 1M alerts
# Load 10 alerts per minute

# Load 100 alerts per minute

# Load 1000 alerts per minute

- **Load 10 alerts per minute**: (details)
- **Load 100 alerts per minute**: (details)
- **Load 1,000 alerts per minute**: (details)
