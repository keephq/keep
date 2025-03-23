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

# Execute the CMD provided in the Dockerfile or as arguments

# Check for REDIS env variable == true
if [ "$REDIS" != "true" ]; then
    # just run gunicorn
    exec "$@"
# else, we want differnt workers for API and for processing
else
    echo "Running with Redis"
    # default number of workers is two
    KEEP_WORKERS=${KEEP_WORKERS:-2}
    echo "KEEP_WORKERS: $KEEP_WORKERS"
    # Run gunicorn with the specified workers
    KEEP_WORKERS=${KEEP_WORKERS} REDIS=true python -m keep.api.arq_worker &
    echo "Running gunicorn with $KEEP_WORKERS workers"
    exec "$@"
fi
