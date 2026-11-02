-- Verification queries for custom schema setup

-- 1. Check if custom schema exists
SELECT nspname AS schema_name, 
       pg_catalog.pg_get_userbyid(nspowner) AS owner
FROM pg_catalog.pg_namespace
WHERE nspname = 'keep_custom';

-- 2. Check current search_path
SHOW search_path;

-- 3. List all Keep-related tables in custom schema
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'keep_custom'
ORDER BY table_name;

-- 4. Count tables in each schema
SELECT table_schema, COUNT(*) as table_count
FROM information_schema.tables
WHERE table_schema IN ('public', 'keep_custom')
  AND table_type = 'BASE TABLE'
GROUP BY table_schema;

-- 5. Check if alembic_version is in custom schema (migration tracking)
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_name = 'alembic_version';

-- 6. Verify the test migration with current_schema() worked
SELECT n.nspname as schema_name, 
       c.relname as index_name
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relname = 'idx_status_started';