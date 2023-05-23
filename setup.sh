#!/bin/bash

STATE_DIRECTORY="state"


# Define secrets for frontend and backend
frontend_secrets=(
  "NEXTAUTH_URL:http://localhost:3000"
  "NEXTAUTH_SECRET:{openssl rand -hex 32}"
  "API_URL:http://backend:8080"
  "AUTH_ENABLED:false"
  "AUTH0_CLIENT_ID:"
  "AUTH0_CLIENT_SECRET:"
  "AUTH0_ISSUER:"
)
backend_secrets=(
  "DATABASE_CONNECTION_STRING:sqlite:////state/db.sqlite3"
  "SECRET_MANAGER_DIRECTORY:state"
  "SECRET_MANAGER_TYPE:FILE"
  "AUTH0_DOMAIN:dev-gsx2mvfi4wfvqjay.us.auth0.com"
  "AUTH0_AUDIENCE:vx2pdcpVnDPaIeFLdzwn3J9M7RZp2KEv"
)

# Function to prompt user for secrets
prompt_for_secrets() {
  local service=$1
  local secrets=("${!2}")

  echo "Setting up secrets for $service..."
  echo "If you do not have a value for a secret, leave it blank and press enter."

  # Loop through the secrets and prompt the user for input
  for secret in "${secrets[@]}"; do
    IFS=':' read -ra secret_info <<< "$secret"
    secret_name=${secret_info[0]}
    default_value=$(IFS=':'; echo "${secret_info[*]:1}")

    # Evaluate command as default value
    if [[ $default_value == \{* ]]; then
      command=$(echo "$default_value" | sed 's/[{}]//g')
      default_value=$(eval "$command")
    fi

    read -p "Enter the $secret_name for $service [Default: $default_value]: " secret_value

    # Use default value if user input is empty
    if [ -z "$secret_value" ]; then
      secret_value=$default_value
    fi

    echo "$secret_name=$secret_value" >> "./$STATE_DIRECTORY/$service.env"
  done
}

# Check if the secrets file exists for the specified service
check_and_create_secrets() {
  local service=$1
  local secrets=("${!2}")

  if [ ! -f "./$STATE_DIRECTORY/$service.env" ]; then
    touch "./$STATE_DIRECTORY/$service.env"
    prompt_for_secrets "$service" secrets[@]
  else
    echo "Environment variable file for $service (./$STATE_DIRECTORY/$service.env) already exists. Skipping..."
  fi
}

# Check the parameter to determine which service to set up
if [ "$1" == "frontend" ]; then
  check_and_create_secrets "frontend" frontend_secrets[@]
elif [ "$1" == "backend" ]; then
  check_and_create_secrets "backend" backend_secrets[@]
else
  check_and_create_secrets "frontend" frontend_secrets[@]
  check_and_create_secrets "backend" backend_secrets[@]
  # echo "Invalid service specified. Usage: ./setup.sh <frontend|backend>"
  # exit 1
fi
