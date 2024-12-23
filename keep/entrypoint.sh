#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Print commands and their arguments as they are executed
set -x

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$0")

python "$SCRIPT_DIR/server_jobs_bg.py" &

# Build the providers cache
{
    keep provider build_cache
} || {
    echo "Failed to build providers cache, skipping"
}

# Create the new command with the environment-specified number of workers
new_cmd=""
found_workers=0
while [ $# -gt 0 ]; do
    if [ "$1" = "--workers" ]; then
        new_cmd="$new_cmd --workers ${GUNICORN_WORKERS:-1}"
        shift 2
        found_workers=1
    else
        new_cmd="$new_cmd $1"
        shift
    fi
done

# If no workers argument was found, add it
if [ $found_workers -eq 0 ]; then
    new_cmd="$new_cmd --workers ${GUNICORN_WORKERS:-1}"
fi

# Execute the modified command
eval exec $new_cmd
