#!/bin/bash

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker first!"
  echo "Start Docker Desktop or run 'sudo systemctl start docker' and try again."
  exit 1
fi

# If Docker is running, proceed with Airflow startup
echo "Docker is running. Starting Airflow..."
export $(grep -v '^#' .env | xargs) && uv run airflow standalone
