#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Print commands and their arguments as they are executed
set -x

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$0")

python "$SCRIPT_DIR/api/background_server_jobs.py" &

# Execute the CMD provided in the Dockerfile or as arguments
exec "$@"