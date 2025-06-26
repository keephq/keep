#!/bin/bash
set -e

# Run a single E2E test configuration
DB_TYPE=${1:-mysql}
echo "Running E2E tests with $DB_TYPE database..."

# Clean up
docker compose -p keep-test down -v || true

# Create docker-compose file
cp tests/e2e_tests/docker-compose-e2e-$DB_TYPE.yml tests/e2e_tests/docker-compose-test.yml

# Build images
echo "Building Docker images..."
docker build -t keep-backend:local -f docker/Dockerfile.api .
docker build -t keep-frontend:local -f docker/Dockerfile.ui keep-ui/

# Replace placeholders
sed -i.bak "s|%KEEPFRONTEND_IMAGE%|keep-frontend:local|g" tests/e2e_tests/docker-compose-test.yml
sed -i.bak "s|%KEEPBACKEND_IMAGE%|keep-backend:local|g" tests/e2e_tests/docker-compose-test.yml
rm tests/e2e_tests/docker-compose-test.yml.bak

# Start services
docker compose -p keep-test -f tests/e2e_tests/docker-compose-test.yml up -d

# Wait a bit
echo "Waiting for services to start..."
sleep 30

# Check services
echo "Checking service health..."
curl -f http://localhost:8080/healthcheck || echo "Backend not ready"
curl -f http://localhost:3000/ || echo "Frontend not ready"

# Run tests
echo "Running E2E tests..."
poetry run pytest -v tests/e2e_tests/test_incident_form_schema_complete.py -n 1

# Clean up
docker compose -p keep-test -f tests/e2e_tests/docker-compose-test.yml down -v
rm tests/e2e_tests/docker-compose-test.yml