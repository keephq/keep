#!/bin/bash

# Wait for the database to be ready (optional, if you use a database)
# sleep 10

# Initialize the database and create an admin user
superset fab create-admin --username admin --firstname Superset --lastname Admin --email admin@superset.com --password admin

# Apply database migrations
superset db upgrade

# Load example data (optional)
# superset load_examples

# Start the Superset server
superset init

# Start the Gunicorn server to serve Superset
gunicorn \
  --bind 0.0.0.0:8088 \
  --workers 3 \
  --timeout 120 \
  "superset.app:create_app()"
