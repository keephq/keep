#!/bin/bash

# Define secrets for frontend and backend
# Todo: read these from a template file (e.g. .env.local.example)
frontend_secrets=("API_KEY" "ANOTHER_SECRET")
backend_secrets=("DATABASE_URL" "JWT_SECRET")

# Function to prompt user for secrets
prompt_for_secrets() {
  local service=$1
  local secrets=("${!2}")

  echo "Setting up secrets for $service..."

  # Loop through the secrets and prompt the user for input
  for secret in "${secrets[@]}"; do
    read -p "Enter the $secret for $service: " secret_value
    echo "$secret=$secret_value" >> "./$service-secrets.env"
  done
}

# Check if the secrets file exists for the specified service
check_and_create_secrets() {
  local service=$1
  local secrets=("${!2}")

  if [ ! -f "./$service-secrets.env" ]; then
    prompt_for_secrets "$service" secrets[@]
  fi
}

# Check the parameter to determine which service to set up
if [ "$1" == "frontend" ]; then
  check_and_create_secrets "frontend" frontend_secrets[@]
elif [ "$1" == "backend" ]; then
  check_and_create_secrets "backend" backend_secrets[@]
else
  echo "Invalid service specified. Usage: ./setup.sh <frontend|backend>"
  exit 1
fi

# Execute docker-compose up as the entry point
exec docker-compose up
