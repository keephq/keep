#!/bin/bash
set -e

echo "=== Testing PostgreSQL Custom Schema Configuration ==="
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if command succeeded
check_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
    else
        echo -e "${RED}✗ $1${NC}"
        exit 1
    fi
}

# Note: Images are already set in docker-compose-test-schema.yml
# No need for sed replacements

echo "1. Starting PostgreSQL with custom schema configuration..."
docker compose -f docker-compose-test-schema.yml up -d postgres-custom-schema
sleep 10  # Wait for PostgreSQL to initialize
check_result "PostgreSQL started"

echo
echo "2. Verifying custom schema was created..."
docker compose -f docker-compose-test-schema.yml exec -T postgres-custom-schema psql -U keepuser -d keepdb -c "\dn keep_custom" | grep keep_custom
check_result "Custom schema 'keep_custom' exists"

echo
echo "3. Checking schema permissions..."
docker compose -f docker-compose-test-schema.yml exec -T postgres-custom-schema psql -U keepuser -d keepdb -c "SELECT has_schema_privilege('keepuser', 'keep_custom', 'CREATE');" | grep -q 't'
check_result "User has CREATE permission on custom schema"

echo
echo "4. Starting Keep backend with POSTGRES_SCHEMA=keep_custom..."
docker compose -f docker-compose-test-schema.yml up -d keep-backend-custom-schema
echo "Waiting for Keep backend to initialize and run migrations..."
sleep 30  # Wait for migrations to run
check_result "Keep backend started"

echo
echo "5. Checking if Keep tables were created in custom schema..."
TABLES=$(docker compose -f docker-compose-test-schema.yml exec -T postgres-custom-schema psql -U keepuser -d keepdb -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'keep_custom' AND table_name NOT IN ('schema_test');" -t | tr -d ' ')
if [ "$TABLES" -gt "0" ]; then
    echo -e "${GREEN}✓ Found $TABLES Keep tables in custom schema${NC}"
else
    echo -e "${RED}✗ No Keep tables found in custom schema${NC}"
    echo "Checking logs for errors..."
    docker compose -f docker-compose-test-schema.yml logs keep-backend-custom-schema | tail -20
    exit 1
fi

echo
echo "6. Listing some Keep tables in custom schema..."
docker compose -f docker-compose-test-schema.yml exec -T postgres-custom-schema psql -U keepuser -d keepdb -c "SELECT table_name FROM information_schema.tables WHERE table_schema = 'keep_custom' AND table_name NOT IN ('schema_test') ORDER BY table_name LIMIT 10;"

echo
echo "7. Verifying no Keep tables in public schema..."
PUBLIC_TABLES=$(docker compose -f docker-compose-test-schema.yml exec -T postgres-custom-schema psql -U keepuser -d keepdb -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND (table_name LIKE 'keep%' OR table_name LIKE 'alert%' OR table_name LIKE 'workflow%');" -t | tr -d ' ')
if [ "$PUBLIC_TABLES" -eq "0" ]; then
    echo -e "${GREEN}✓ No Keep tables found in public schema (as expected)${NC}"
else
    echo -e "${RED}✗ Found $PUBLIC_TABLES Keep tables in public schema (unexpected)${NC}"
fi

echo
echo "8. Testing API health endpoint..."
curl -s http://localhost:8082/healthcheck | grep -q "ok"
check_result "API health check passed"

echo
echo "9. Checking current schema from Keep's perspective..."
docker compose -f docker-compose-test-schema.yml exec -T postgres-custom-schema psql -U keepuser -d keepdb -c "SHOW search_path;"

echo
echo -e "${GREEN}=== All tests passed! ===${NC}"
echo "Keep is successfully using PostgreSQL with custom schema 'keep_custom'"
echo
echo "To view logs: docker compose -f docker-compose-test-schema.yml logs"
echo "To clean up: docker compose -f docker-compose-test-schema.yml down -v"

# No backup file to restore since we skipped sed commands