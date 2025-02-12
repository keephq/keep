#!/bin/bash

# Function to import dashboards
import_dashboards() {
    local dashboard_file="/app/dashboards/dashboards.zip"
    local export_dir="/tmp/dashboard_export"

    echo "Preparing to import dashboards..."

    # Create export directory if it doesn't exist
    mkdir -p "$export_dir"

    # Unzip using Python
    python3 -c "import zipfile; import os; os.makedirs('$export_dir', exist_ok=True); zipfile.ZipFile('$dashboard_file', 'r').extractall('$export_dir')"

    if [ -n "$KEEP_SUPERSET_DB" ]; then
        echo "KEEP_SUPERSET_DB is set to $KEEP_SUPERSET_DB, patching database configuration..."
        # Update database configuration in the exported files
        find "$export_dir" -type f -name "*.yaml" -exec sed -i "s|sqlite:////shared-db/db2|sqlite:////$KEEP_SUPERSET_DB|g" {} +
    fi

    # Create new zip using Python
    python3 -c "import zipfile; import os; z = zipfile.ZipFile('/tmp/patched_dashboards.zip', 'w'); [z.write(os.path.join(root, f), os.path.join(root.replace('$export_dir', ''), f)) for root, _, files in os.walk('$export_dir') for f in files]"

    echo "Importing dashboards..."
    superset import_dashboards --username admin -p /tmp/patched_dashboards.zip
}

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
  "superset.app:create_app()" &

# import the dashboards
echo "Keep: sleeping 5"
sleep 5
echo "Keep: importing dashboards"
import_dashboards

# wait forever
sleep infinity
