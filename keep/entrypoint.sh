#!/bin/bash

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

# Check for REDIS env variable == true
if [ "$REDIS" != "true" ]; then
    # Just run gunicorn for the API
    exec "$@"
# else, we want different workers for API and for processing
else
    echo "Running with Redis"

    # In production, always use Gunicorn for ARQ workers
    # default number of workers is two
    KEEP_WORKERS=${KEEP_WORKERS:-2}
    ARQ_WORKER_PORT=${ARQ_WORKER_PORT:-8001}
    ARQ_WORKER_TIMEOUT=${ARQ_WORKER_TIMEOUT:-120}
    LOG_LEVEL=${LOG_LEVEL:-INFO}

    echo "Starting ARQ workers under Gunicorn (workers: $KEEP_WORKERS)"

    # Run Gunicorn directly for ARQ workers
    PYTHONPATH=$PYTHONPATH \
    REDIS=true \
    KEEP_WORKERS=$KEEP_WORKERS \
    LOG_LEVEL=$LOG_LEVEL \
    gunicorn \
        --bind "0.0.0.0:$ARQ_WORKER_PORT" \
        --workers $KEEP_WORKERS \
        --worker-class "keep.api.arq_worker_gunicorn.ARQGunicornWorker" \
        --timeout $ARQ_WORKER_TIMEOUT \
        --log-level $LOG_LEVEL \
        --access-logfile - \
        --error-logfile - \
        --name "arq_worker" \
        "keep.api.arq_worker_gunicorn:create_app()" &

    KEEP_ARQ_PID=$!

    # Give ARQ workers time to start up
    sleep 2

    echo "Running API gunicorn"
    exec "$@" &

    KEEP_API_PID=$!

    # Wait for any to exit
    wait -n $KEEP_ARQ_PID $KEEP_API_PID

    # One exited — kill the other
    kill $KEEP_ARQ_PID $KEEP_API_PID 2>/dev/null || true

    # Exit to trigger container restart
    exit 1
fi
