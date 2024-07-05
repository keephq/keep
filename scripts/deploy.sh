#!/bin/bash

# Get the company name from the user
read -p "Enter the company name: " COMPANY_NAME
PROJECT_NAME="keep-${COMPANY_NAME}"

# Initialize and read environment variables
CREATE_GCP_PROJECT_ENABLED=${CREATE_GCP_PROJECT_ENABLED:-"true"}
ASSIGN_GCP_BILLING_ENABLED=${ASSIGN_GCP_BILLING_ENABLED:-"true"}
BILLING_ACCOUNT_NAME=${BILLING_ACCOUNT_NAME:-"keephq"}
CREATE_SERVICE_ACCOUNT_ENABLED=${CREATE_SERVICE_ACCOUNT_ENABLED:-"true"}

# MySQL related variables
CREATE_SQL_INSTANCE_ENABLED=${CREATE_SQL_INSTANCE_ENABLED:-"true"}
MYSQL_INSTANCE_NAME=${MYSQL_INSTANCE_NAME:-"keep-db"}
MYSQL_TIER=${MYSQL_TIER:-"db-f1-micro"}
MYSQL_STORAGE_SIZE=${MYSQL_STORAGE_SIZE:-10}  # in GB
MYSQL_SORT_BUFFER_SIZE=${MYSQL_SORT_BUFFER_SIZE:-256000000}

# Keep related variables
CREATE_GCP_SECRETS_ENABLED=${CREATE_GCP_SECRETS_ENABLED:-"true"}
KEEP_DEFAULT_USERNAME=${KEEP_DEFAULT_USERNAME:-"admin"}
KEEP_DEFAULT_PASSWORD=${KEEP_DEFAULT_PASSWORD:-"admin"}
# generate random string for JWT secret
KEEP_JWT_SECRET=${KEEP_JWT_SECRET:-$(openssl rand -base64 32)}

# GCP Cloud Run variables
CREATE_CLOUD_RUN_SERVICE_ENABLED=${CREATE_CLOUD_RUN_SERVICE_ENABLED:-"true"}
AUTH_TYPE=SINGLE_TENANT
SERVICE_NAME=keep-api
KEEP_API_URL="api.${COMPANY_NAME}.keephq.dev"
GOOGLE_CLOUD_PROJECT="${PROJECT_NAME}"
CLOUD_TRACE_ENABLED=true
SECRET_MANAGER_TYPE=gcp
STORAGE_MANAGER_TYPE=gcp
PUSHER_DISABLED=true
OTEL_TRACES_SAMPLER=parentbased_traceidratio
OTEL_TRACES_SAMPLER_ARG=0.3
DB_CONNECTION_NAME="${PROJECT_NAME}:us-central1:$MYSQL_INSTANCE_NAME"

# Cloudflare variables
CREATE_CLOUDFLARE_DNS_RECORDS=${CREATE_CLOUDFLARE_DNS_RECORDS:-"true"}
CLOUDFLARE_API_TOKEN=${CLOUDFLARE_API_TOKEN:-""}
CLOUDFLARE_ZONE_ID=${CLOUDFLARE_ZONE_ID:-""}

# Function to print logs
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Step 0: Check if gcloud is installed
check_gcloud_installed() {
    if ! command -v gcloud &> /dev/null; then
        log "gcloud could not be found. Please install the Google Cloud SDK before running this script."
        exit 1
    fi
}

# Step 0c: Check if curl and jq are installed
check_curl_jq_installed() {
    if ! command -v curl &> /dev/null; then
        log "curl could not be found. Please install curl before running this script."
        exit 1
    fi
    if ! command -v jq &> /dev/null; then
        log "jq could not be found. Please install jq before running this script."
        exit 1
    fi
}

check_cloudflare_api_token() {
    if [ "$CREATE_CLOUDFLARE_DNS_RECORDS" == "true" ]; then
        if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
            log "CLOUDFLARE_API_TOKEN is not set. Please set the Cloudflare API token before running this script."
            exit 1
        fi

        local RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
        -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
        -H "Content-Type:application/json")
        local SUCCESS=$(echo "${RESPONSE}" | jq -r '.success')

        if [ "${SUCCESS}" == "false" ]; then
            log "Could not authenticate to cloudflare: $(echo "${RESPONSE}" | jq -r '.errors')"
            exit 1
        fi
    fi
}

# Check for necessary installations
check_gcloud_installed
check_curl_jq_installed
check_cloudflare_api_token

#############
# Functions #
#############

# Function to create DNS record in Cloudflare
create_dns_record() {
    local TYPE=$1
    local NAME=$2
    local CONTENT=$3
    local PROXY_STATUS=${4:-false}
    local TTL=${5:-1}  # Default to auto TTL

    log "Creating DNS record in Cloudflare: TYPE=${TYPE}, NAME=${NAME}, CONTENT=${CONTENT}, PROXY_STATUS=${PROXY_STATUS}, TTL=${TTL}"

    local DATA=$(cat <<EOF
{
    "type": "${TYPE}",
    "name": "${NAME}",
    "content": "${CONTENT}",
    "proxied": ${PROXY_STATUS},
    "ttl": ${TTL}
}
EOF
    )

    local RESPONSE=$(curl --silent --request POST \
        --url "https://api.cloudflare.com/client/v4/zones/${CLOUDFLARE_ZONE_ID}/dns_records" \
        --header "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
        --header "Content-Type: application/json" \
        --data "${DATA}")

    local SUCCESS=$(echo "${RESPONSE}" | jq -r '.success')

    if [ "${SUCCESS}" == "true" ]; then
        log "DNS record created successfully: ${NAME}"
    else
        log "Failed to create DNS record: $(echo "${RESPONSE}" | jq -r '.errors')"
    fi
}

create_gcp_env() {
    log "Starting GCP Environment creation for project $PROJECT_NAME..."

    # Check if GCP project already exists
    EXISTING_PROJECT=$(gcloud projects list --filter="name:${PROJECT_NAME}" --format="value(name)")

    if [ -n "$EXISTING_PROJECT" ]; then
        log "GCP project ${PROJECT_NAME} already exists. Skipping creation."
    else
        log "Creating GCP project ${PROJECT_NAME}..."
        gcloud projects create "${PROJECT_NAME}" --set-as-default
        # Add more GCP setup commands as needed
        log "GCP project ${PROJECT_NAME} created successfully."
    fi
}

enable_compute_engine_api() {
    log "Checking if Compute Engine API is enabled..."

    COMPUTE_ENGINE_API_ENABLED=$(gcloud services list --enabled --filter="name:compute.googleapis.com" --format="value(name)")

    if [ -z "$COMPUTE_ENGINE_API_ENABLED" ]; then
        log "Compute Engine API is not enabled. Enabling Compute Engine API..."
        gcloud services enable compute.googleapis.com --project="${PROJECT_NAME}"
        log "Compute Engine API enabled successfully."
    else
        log "Compute Engine API is already enabled."
    fi
}

connect_billing_account() {
    log "Connecting GCP project ${PROJECT_NAME} to billing account ${BILLING_ACCOUNT_NAME}..."

    # tb: I opened https://issuetracker.google.com/issues/350764038 but the issue was capital NAME vs name (wtf? :X)
    BILLING_ACCOUNT_ID=$(gcloud beta billing accounts list --filter="NAME:${BILLING_ACCOUNT_NAME}" --format="value(name)")

    if [ -z "$BILLING_ACCOUNT_ID" ]; then
        log "Billing account ${BILLING_ACCOUNT_NAME} not found. Please check the billing account name and try again."
        exit 1
    fi

    # Check if the project is already linked to a billing account
    CURRENT_BILLING_ACCOUNT=$(gcloud beta billing projects describe "${PROJECT_NAME}" --format="value(billingAccountName)")

    if [ "$CURRENT_BILLING_ACCOUNT" == "billingAccounts/$BILLING_ACCOUNT_ID" ]; then
        log "GCP project ${PROJECT_NAME} is already connected to billing account ${BILLING_ACCOUNT_NAME}. Skipping connection."
    else
        log "Linking GCP project ${PROJECT_NAME} to billing account ${BILLING_ACCOUNT_NAME}..."
        gcloud beta billing projects link "${PROJECT_NAME}" --billing-account="${BILLING_ACCOUNT_ID}"
        log "GCP project ${PROJECT_NAME} connected to billing account ${BILLING_ACCOUNT_NAME} successfully."
    fi
}

create_service_account() {
    log "Creating service account 'keep-api' for project $PROJECT_NAME..."

    # Check if service account already exists
    EXISTING_SERVICE_ACCOUNT=$(gcloud iam service-accounts list --filter="name:keep-api" --format="value(email)" --project="${PROJECT_NAME}")

    if [ -n "$EXISTING_SERVICE_ACCOUNT" ]; then
        log "Service account 'keep-api' already exists. Skipping creation."
    else
        log "Creating service account 'keep-api'..."
        gcloud iam service-accounts create keep-api --project="${PROJECT_NAME}" --display-name="keep-api"

        # Assign roles to the service account
        gcloud projects add-iam-policy-binding "${PROJECT_NAME}" --member="serviceAccount:keep-api@${PROJECT_NAME}.iam.gserviceaccount.com" --role="roles/cloudsql.client"
        gcloud projects add-iam-policy-binding "${PROJECT_NAME}" --member="serviceAccount:keep-api@${PROJECT_NAME}.iam.gserviceaccount.com" --role="roles/cloudsql.user"
        gcloud projects add-iam-policy-binding "${PROJECT_NAME}" --member="serviceAccount:keep-api@${PROJECT_NAME}.iam.gserviceaccount.com" --role="roles/secretmanager.admin"
        gcloud projects add-iam-policy-binding "${PROJECT_NAME}" --member="serviceAccount:keep-api@${PROJECT_NAME}.iam.gserviceaccount.com" --role="roles/storage.admin"

        log "Service account 'keep-api' created and roles assigned successfully."
    fi
}

create_sql_instance() {
    log "Creating MySQL instance '${MYSQL_INSTANCE_NAME}' in project $PROJECT_NAME..."

    # Check if the MySQL instance already exists
    EXISTING_INSTANCE=$(gcloud sql instances list --filter="name:${MYSQL_INSTANCE_NAME}" --format="value(name)" --project="${PROJECT_NAME}")
    local MYSQL_ROOT_PASSWORD=$(openssl rand -base64 16)

    if [ -n "$EXISTING_INSTANCE" ]; then
        log "MySQL instance '${MYSQL_INSTANCE_NAME}' already exists, setting root password"
        gcloud sql users set-password root --host=% --instance="${MYSQL_INSTANCE_NAME}" --password="${MYSQL_ROOT_PASSWORD}" --project="${PROJECT_NAME}"
    else
        log "Creating MySQL instance '${MYSQL_INSTANCE_NAME}'..."
        gcloud sql instances create "${MYSQL_INSTANCE_NAME}" \
            --project="${PROJECT_NAME}" \
            --tier="${MYSQL_TIER}" \
            --storage-size="${MYSQL_STORAGE_SIZE}" \
            --database-version="MYSQL_8_0_26" \
            --root-password="${MYSQL_ROOT_PASSWORD}"
        log "Setting MySQL flag 'sort_buffer_size' to ${MYSQL_SORT_BUFFER_SIZE}..."
        gcloud sql instances patch "${MYSQL_INSTANCE_NAME}" \
            --project="${PROJECT_NAME}" \
            --database-flags sort_buffer_size="${MYSQL_SORT_BUFFER_SIZE}",cloudsql_iam_authentication=on
        log "MySQL instance '${MYSQL_INSTANCE_NAME}' created and configured successfully."
    fi

    log "Creating MySQL user for service account 'keep-api' in instance '${MYSQL_INSTANCE_NAME}'..."
    gcloud sql users create "keep-api@${PROJECT_NAME}.iam.gserviceaccount.com" \
        --instance="${MYSQL_INSTANCE_NAME}" \
        --type=CLOUD_IAM_SERVICE_ACCOUNT \
        --project="${PROJECT_NAME}" \
        --quiet || log "MySQL user already exists."
    log "### Please use the following root password when prompted: ${MYSQL_ROOT_PASSWORD} ###"
    gcloud beta sql connect "${MYSQL_INSTANCE_NAME}" --project="${PROJECT_NAME}" --user=root <<EOF
GRANT ALL PRIVILEGES ON *.* TO 'keep-api'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EOF
    log "Created MySQL user for service account 'keep-api' in instance '${MYSQL_INSTANCE_NAME}'..."
    exit 1
}

create_gcp_secrets() {
    log "Creating Keep GCP secrets..."

    gcloud services enable secretmanager.googleapis.com --project="${PROJECT_NAME}"

    # Create the KEEP_DEFAULT_USERNAME secret
    if gcloud secrets describe keep-default-username --project="${PROJECT_NAME}" &> /dev/null; then
        log "Secret keep-default-username already exists. Skipping creation."
    else
        echo -n "${KEEP_DEFAULT_USERNAME}" | gcloud secrets create keep-default-username --data-file=- --project="${PROJECT_NAME}"
        log "Secret keep-default-username created successfully."
    fi

    # Create the KEEP_DEFAULT_PASSWORD secret
    if gcloud secrets describe keep-default-password --project="${PROJECT_NAME}" &> /dev/null; then
        log "Secret keep-default-password already exists. Skipping creation."
    else
        echo -n "${KEEP_DEFAULT_PASSWORD}" | gcloud secrets create keep-default-password --data-file=- --project="${PROJECT_NAME}"
        log "Secret keep-default-password created successfully."
    fi

    # Create the KEEP_JWT_SECRET secret
    if gcloud secrets describe keep-jwt-secret --project="${PROJECT_NAME}" &> /dev/null; then
        log "Secret keep-jwt-secret already exists. Skipping creation."
    else
        echo -n "${KEEP_JWT_SECRET}" | gcloud secrets create keep-jwt-secret --data-file=- --project="${PROJECT_NAME}"
        log "Secret keep-jwt-secret created successfully."
    fi
}

enable_cloud_run_api() {
    log "Checking if Cloud Run API is enabled..."

    CLOUD_RUN_API_ENABLED=$(gcloud services list --enabled --filter="name:run.googleapis.com" --format="value(name)")

    if [ -z "$CLOUD_RUN_API_ENABLED" ]; then
        log "Cloud Run API is not enabled. Enabling Cloud Run API..."
        gcloud services enable run.googleapis.com --project="${PROJECT_NAME}"
        log "Cloud Run API enabled successfully."
    else
        log "Cloud Run API is already enabled."
    fi
}

create_cloud_run_service() {
    log "Creating Cloud Run service '${SERVICE_NAME}'..."

    # Check if the region is us-central1, if not find the region
    REGION=$(gcloud run regions list --format="value(locationId)" | grep -m 1 "us-central1")
    if [ -z "$REGION" ]; then
        REGION=$(gcloud run regions list --format="value(locationId)" | head -n 1)
        log "Region 'us-central1' is not available. Using default region '${REGION}'."
    else
        log "Using region 'us-central1'."
    fi

    # Deploy the Cloud Run service
    gcloud run deploy "${SERVICE_NAME}" \
        --image="us-central1-docker.pkg.dev/keephq/keep/keep-api:latest" \
        --region="${REGION}" \
        --cpu=4 \
        --memory=4Gi \
        --min-instances=1 \
        --platform=managed \
        --service-account="keep-api@${PROJECT_NAME}.iam.gserviceaccount.com" \
        --allow-unauthenticated \
        --add-cloudsql-instances="${DB_CONNECTION_NAME}" \
        --set-env-vars AUTH_TYPE="${AUTH_TYPE}",SERVICE_NAME="${SERVICE_NAME}",KEEP_API_URL="https://${KEEP_API_URL}",GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}",CLOUD_TRACE_ENABLED="${CLOUD_TRACE_ENABLED}",SECRET_MANAGER_TYPE="${SECRET_MANAGER_TYPE}",STORAGE_MANAGER_TYPE="${STORAGE_MANAGER_TYPE}",PUSHER_DISABLED="${PUSHER_DISABLED}",OTEL_TRACES_SAMPLER="${OTEL_TRACES_SAMPLER}",OTEL_TRACES_SAMPLER_ARG="${OTEL_TRACES_SAMPLER_ARG}",DB_CONNECTION_NAME="${DB_CONNECTION_NAME}" \
        --update-secrets KEEP_DEFAULT_USERNAME=keep-default-username:latest \
        --update-secrets KEEP_DEFAULT_PASSWORD=keep-default-password:latest \
        --update-secrets KEEP_JWT_SECRET=keep-jwt-secret:latest
        # --update-secrets PUSHER_APP_ID=pusher-app-id:latest \
        # --update-secrets PUSHER_APP_KEY=pusher-app-key:latest \
        # --update-secrets PUSHER_APP_SECRET=pusher-app-secret:latest

    if [ "$CREATE_CLOUDFLARE_DNS_RECORDS" == "true" ]; then
        create_dns_record "CNAME" "api.$COMPANY_NAME" "ghs.googlehosted.com."
        gcloud beta run domain-mappings create \
            --service="${SERVICE_NAME}" \
            --domain="${KEEP_API_URL}" \
            --project="${PROJECT_NAME}" \
            --region="${REGION}" \
            --async
    fi

    log "Cloud Run service '${SERVICE_NAME}' created and configured successfully."
}


#########################
# Main script execution #
#########################

# Step 1: Create GCP Environment
if [ "$CREATE_GCP_PROJECT_ENABLED" == "true" ]; then
    create_gcp_env
else
    log "GCP Environment creation skipped."
fi

# Step 2: Connect GCP Project to Billing Account
if [ "$ASSIGN_GCP_BILLING_ENABLED" == "true" ]; then
    connect_billing_account
else
    log "Billing account connection skipped."
fi

# Step 3: Create Service Account for keep-api
if [ "$CREATE_SERVICE_ACCOUNT_ENABLED" == "true" ]; then
    create_service_account
else
    log "Service account creation skipped."
fi

# Step 4: Create MySQL Instance in Cloud SQL
if [ "$CREATE_SQL_INSTANCE_ENABLED" == "true" ]; then
    enable_compute_engine_api
    create_sql_instance
else
    log "MySQL instance creation skipped."
fi

# Step 5: Create Keep GCP Secrets
if [ "$CREATE_GCP_SECRETS_ENABLED" == "true" ]; then
    create_gcp_secrets
else
    log "GCP secrets creation skipped."
fi

# Step 6a: Check if Cloud Run API is enabled
# Step 6b: Create Cloud Run Service
if [ "$CREATE_CLOUD_RUN_SERVICE_ENABLED" == "true" ]; then
    enable_cloud_run_api
    create_cloud_run_service
else
    log "Cloud Run service creation skipped."
fi
