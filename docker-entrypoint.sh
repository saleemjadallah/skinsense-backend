#!/bin/bash
set -e

# Function to handle SIGTERM signal for graceful shutdown
_term() {
  echo "Caught SIGTERM signal! Waiting for current requests to finish..."
  
  # Give nginx time to stop routing new traffic to this container
  sleep 5
  
  # Send SIGTERM to the FastAPI process for graceful shutdown
  kill -TERM "$child" 2>/dev/null
  
  # Wait for the process to finish (max 30 seconds)
  timeout=30
  while kill -0 "$child" 2>/dev/null && [ $timeout -gt 0 ]; do
    echo "Waiting for process to finish... ($timeout seconds remaining)"
    sleep 1
    timeout=$((timeout - 1))
  done
  
  # Force kill if still running
  if kill -0 "$child" 2>/dev/null; then
    echo "Force killing process after timeout"
    kill -KILL "$child" 2>/dev/null
  fi
  
  echo "Graceful shutdown complete"
  exit 0
}

# Trap SIGTERM and SIGINT signals
trap _term SIGTERM SIGINT

# Log startup
echo "Starting SkinSense AI Backend (Service Color: ${SERVICE_COLOR:-unknown})"

# Run the FastAPI application in the background
exec "$@" &

# Store the PID
child=$!

# Wait for the child process
wait "$child"
exit_status=$?

echo "Process exited with status $exit_status"
exit $exit_status