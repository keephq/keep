#!/bin/bash

# Start the REST API with 4 workers
echo "Starting REST mode..."
gunicorn "keep.api.api:get_app(mode='rest')" \
  --bind 0.0.0.0:8080 \
  --workers 4 \
  -k uvicorn.workers.UvicornWorker \
  -c /venv/lib/python3.11/site-packages/keep/api/config.py &

# Check if REDIS is true, and start the worker mode if it is
# I'm using random port 1234 because it doesn't matter
if [ "$REDIS" = "true" ]; then
  echo "Starting worker mode..."
  gunicorn "keep.api.api:get_app(mode='worker')" \
    --workers 4 \
    -b 0.0.0.0:1234 \
    -k uvicorn.workers.UvicornWorker &
fi

# Wait for all background processes to complete
wait -n

# Exit with the status of the first process to exit
exit $?
