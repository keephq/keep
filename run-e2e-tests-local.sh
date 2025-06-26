#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Keep E2E Test Suite ===${NC}\n"

# Function to run tests for a specific configuration
run_test_configuration() {
    local DB_TYPE=$1
    local REDIS_ENABLED=$2
    local TEST_NAME="$DB_TYPE$([ "$REDIS_ENABLED" = "true" ] && echo "-with-redis" || echo "-without-redis")"
    
    echo -e "\n${YELLOW}Running E2E tests: $TEST_NAME${NC}"
    echo "----------------------------------------"
    
    # Clean up any existing containers
    echo "Cleaning up existing containers..."
    docker compose -p keep-$TEST_NAME down -v || true
    
    # Create modified docker-compose file
    echo "Creating docker-compose configuration..."
    cp tests/e2e_tests/docker-compose-e2e-$DB_TYPE.yml tests/e2e_tests/docker-compose-$TEST_NAME.yml
    
    # Build images locally
    echo "Building Docker images..."
    docker build -t keep-backend:local -f docker/Dockerfile.api .
    docker build -t keep-frontend:local -f docker/Dockerfile.ui keep-ui/
    
    # Replace image placeholders
    sed -i.bak "s|%KEEPFRONTEND_IMAGE%|keep-frontend:local|g" tests/e2e_tests/docker-compose-$TEST_NAME.yml
    sed -i.bak "s|%KEEPBACKEND_IMAGE%|keep-backend:local|g" tests/e2e_tests/docker-compose-$TEST_NAME.yml
    rm tests/e2e_tests/docker-compose-$TEST_NAME.yml.bak
    
    # Set environment variables
    export COMPOSE_PROJECT_NAME=keep-$TEST_NAME
    export MYSQL_ROOT_PASSWORD=keep
    export MYSQL_DATABASE=keep
    export POSTGRES_USER=keepuser
    export POSTGRES_PASSWORD=keeppassword
    export POSTGRES_DB=keepdb
    export EE_ENABLED=true
    
    if [ "$REDIS_ENABLED" = "true" ]; then
        export REDIS=true
        export REDIS_HOST=keep-redis
        export REDIS_PORT=6379
    else
        export REDIS=false
    fi
    
    # Start services
    echo "Starting services..."
    docker compose -f tests/e2e_tests/docker-compose-$TEST_NAME.yml up -d
    
    # Wait for services to be ready
    echo "Waiting for services to be ready..."
    sleep 10
    
    # Function to check service health
    wait_for_service() {
        local service_name=$1
        local check_command=$2
        local max_attempts=${3:-30}
        local attempt=1
        
        echo -n "Waiting for $service_name..."
        while ! eval $check_command &>/dev/null; do
            if [ $attempt -eq $max_attempts ]; then
                echo -e " ${RED}FAILED${NC}"
                echo "Service $service_name did not become ready in time"
                docker compose -f tests/e2e_tests/docker-compose-$TEST_NAME.yml logs | tail -50
                return 1
            fi
            echo -n "."
            sleep 2
            attempt=$((attempt + 1))
        done
        echo -e " ${GREEN}OK${NC}"
    }
    
    # Check database
    if [ "$DB_TYPE" = "mysql" ]; then
        wait_for_service "MySQL" "docker compose -f tests/e2e_tests/docker-compose-$TEST_NAME.yml exec -T keep-database mysqladmin ping -h localhost --silent"
    elif [ "$DB_TYPE" = "postgres" ]; then
        wait_for_service "PostgreSQL" "docker compose -f tests/e2e_tests/docker-compose-$TEST_NAME.yml exec -T keep-database pg_isready -h localhost -U keepuser"
    fi
    
    # Check services
    wait_for_service "Keep Backend" "curl --output /dev/null --silent --fail http://localhost:8080/healthcheck"
    wait_for_service "Keep Frontend" "curl --output /dev/null --silent --fail http://localhost:3000/"
    wait_for_service "Keep Backend (DB Auth)" "curl --output /dev/null --silent --fail http://localhost:8081/healthcheck"
    wait_for_service "Keep Frontend (DB Auth)" "curl --output /dev/null --silent --fail http://localhost:3001/"
    wait_for_service "Prometheus" "curl --output /dev/null --silent --fail http://localhost:9090/-/healthy"
    wait_for_service "Grafana" "curl --output /dev/null --silent --fail http://localhost:3002/api/health"
    
    # Run tests
    echo -e "\n${BLUE}Running E2E tests...${NC}"
    if poetry run pytest -v tests/e2e_tests/ -n 4 --dist=loadfile; then
        echo -e "${GREEN}✓ Tests passed for $TEST_NAME${NC}"
        TEST_RESULTS="$TEST_RESULTS\n${GREEN}✓ $TEST_NAME${NC}"
    else
        echo -e "${RED}✗ Tests failed for $TEST_NAME${NC}"
        TEST_RESULTS="$TEST_RESULTS\n${RED}✗ $TEST_NAME${NC}"
        FAILED_TESTS="$FAILED_TESTS $TEST_NAME"
        
        # Collect logs on failure
        echo "Collecting logs..."
        mkdir -p test-logs
        docker compose -f tests/e2e_tests/docker-compose-$TEST_NAME.yml logs > test-logs/$TEST_NAME.log
    fi
    
    # Clean up
    echo "Cleaning up..."
    docker compose -f tests/e2e_tests/docker-compose-$TEST_NAME.yml down -v
    rm tests/e2e_tests/docker-compose-$TEST_NAME.yml
}

# Initialize results tracking
TEST_RESULTS=""
FAILED_TESTS=""

# Check if specific test is requested
if [ "$1" ]; then
    case "$1" in
        "mysql-redis")
            run_test_configuration "mysql" "true"
            ;;
        "postgres")
            run_test_configuration "postgres" "false"
            ;;
        "sqlite")
            run_test_configuration "sqlite" "false"
            ;;
        *)
            echo "Unknown test configuration: $1"
            echo "Available options: mysql-redis, postgres, sqlite"
            exit 1
            ;;
    esac
else
    # Run all test configurations
    echo "Running full E2E test suite (this will take some time)..."
    
    # Install Playwright if not already installed
    echo "Ensuring Playwright is installed..."
    poetry run playwright install --with-deps
    
    # Run each configuration
    run_test_configuration "mysql" "true"
    run_test_configuration "postgres" "false"
    run_test_configuration "sqlite" "false"
fi

# Print summary
echo -e "\n${BLUE}=== Test Summary ===${NC}"
echo -e "$TEST_RESULTS"

if [ -n "$FAILED_TESTS" ]; then
    echo -e "\n${RED}Some tests failed. Check test-logs/ for details.${NC}"
    exit 1
else
    echo -e "\n${GREEN}All tests passed!${NC}"
fi