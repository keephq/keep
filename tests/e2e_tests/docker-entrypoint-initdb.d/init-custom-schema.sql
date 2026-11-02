-- Create custom schema for Keep
CREATE SCHEMA IF NOT EXISTS keep_custom;

-- Grant all necessary permissions to the keepuser
GRANT USAGE, CREATE ON SCHEMA keep_custom TO keepuser;

-- Set search_path for the user (optional, as Keep will handle this)
ALTER USER keepuser SET search_path TO keep_custom, public;

-- Create a test table to verify schema is working
CREATE TABLE keep_custom.schema_test (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message TEXT DEFAULT 'Schema keep_custom is working!'
);

-- Insert a test record
INSERT INTO keep_custom.schema_test (message) VALUES ('Custom schema initialized successfully');

-- Grant permissions on the test table
GRANT ALL PRIVILEGES ON TABLE keep_custom.schema_test TO keepuser;
GRANT USAGE, SELECT ON SEQUENCE keep_custom.schema_test_id_seq TO keepuser;

-- Log the initialization
DO $$
BEGIN
    RAISE NOTICE 'Custom schema keep_custom created and configured for Keep';
END $$;