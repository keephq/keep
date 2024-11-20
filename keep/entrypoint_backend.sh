#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Print commands and their arguments as they are executed
set -x

# Execute background taasks
poetry run python keep/cli/cli.py background-server-jobs &

# Execute the CMD provided in the Dockerfile or as arguments
exec "$@"