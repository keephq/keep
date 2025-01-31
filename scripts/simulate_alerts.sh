#!/bin/bash

# Check if the number of processes to run is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <number_of_processes>"
  exit 1
fi

# Number of processes to run
NUM_PROCESSES=$1

ROOT="$(dirname $0)/.."

# Function to start the processes
start_processes() {
  for ((i=0; i<NUM_PROCESSES; i++)); do
    "${ROOT}/.venv/bin/python" "${ROOT}/scripts/simulate_alerts.py" &
    PIDS[$i]=$!
  done
}

# Function to stop the processes
stop_processes() {
  echo "Stopping processes..."
  for PID in "${PIDS[@]}"; do
    kill $PID
  done
}

# Trap the CTRL+C signal to stop the processes
trap "stop_processes" SIGINT

# Start the processes
start_processes

# Wait for CTRL+C
echo "Running $NUM_PROCESSES processes. Press CTRL+C to stop."
wait
