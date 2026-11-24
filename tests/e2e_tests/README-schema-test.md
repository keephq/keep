# Testing PostgreSQL Custom Schema Configuration

This directory contains test files to verify Keep's PostgreSQL custom schema functionality.

## Files

- `docker compose-test-schema.yml` - Docker Compose configuration with custom schema setup
- `docker-entrypoint-initdb.d/init-custom-schema.sql` - PostgreSQL initialization script
- `test-custom-schema.sh` - Automated test script
- `verify-schema.sql` - SQL queries to manually verify schema setup

## Quick Test

Run the automated test:
```bash
cd tests/e2e_tests
./test-custom-schema.sh
```

## Manual Testing

1. Start the services:
```bash
# Set image environment variables (or use defaults)
export KEEPBACKEND_IMAGE="us-central1-docker.pkg.dev/keephq/keep/keep-api:latest"
export KEEPFRONTEND_IMAGE="us-central1-docker.pkg.dev/keephq/keep/keep-ui:latest"

# Start services
docker compose -f docker compose-test-schema.yml up -d
```

2. Wait for initialization (about 30 seconds for migrations)

3. Verify schema setup:
```bash
# Check if custom schema was created
docker compose -f docker compose-test-schema.yml exec postgres-custom-schema \
  psql -U keepuser -d keepdb -c "\dn keep_custom"

# Run verification queries
docker compose -f docker compose-test-schema.yml exec postgres-custom-schema \
  psql -U keepuser -d keepdb -f /docker-entrypoint-initdb.d/verify-schema.sql

# Check Keep logs
docker compose -f docker compose-test-schema.yml logs keep-backend-custom-schema | grep -i schema
```

4. Access Keep UI at http://localhost:3002 to verify functionality

## What's Being Tested

1. **Schema Creation**: Custom schema `keep_custom` is created with proper permissions
2. **Environment Variable**: `POSTGRES_SCHEMA=keep_custom` is properly handled
3. **Table Creation**: All Keep tables are created in the custom schema, not in public
4. **Migrations**: Alembic migrations run successfully in the custom schema
5. **Application Function**: Keep operates normally with the custom schema

## Configuration Details

The test uses:
- PostgreSQL 13
- Custom schema name: `keep_custom`
- Database user: `keepuser`
- Database name: `keepdb`
- Keep backend port: 8082
- Keep frontend port: 3002
- PostgreSQL port: 5434

## Cleanup

Remove all test containers and volumes:
```bash
docker compose -f docker compose-test-schema.yml down -v
```

## Troubleshooting

If tests fail:

1. Check Keep backend logs for migration errors:
   ```bash
   docker compose -f docker compose-test-schema.yml logs keep-backend-custom-schema
   ```

2. Connect to PostgreSQL to inspect:
   ```bash
   docker compose -f docker compose-test-schema.yml exec postgres-custom-schema \
     psql -U keepuser -d keepdb
   ```

3. Verify environment variables:
   ```bash
   docker compose -f docker compose-test-schema.yml exec keep-backend-custom-schema env | grep -E "(POSTGRES_SCHEMA|DATABASE_CONNECTION)"
   ```