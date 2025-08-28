#!/bin/bash

# Fix network issues before deployment
echo "🔧 Fixing Docker network issues..."

# Stop all containers first
echo "Stopping containers..."
docker stop $(docker ps -aq) 2>/dev/null || true

# Remove the problematic network
echo "Removing old network..."
docker network rm skinsense_network 2>/dev/null || true
docker network rm skinsense-network 2>/dev/null || true

# Remove any other conflicting networks
docker network prune -f

# Clean up containers
echo "Cleaning up containers..."
docker container prune -f

# Create the network fresh
echo "Creating fresh network..."
docker network create --driver bridge --subnet 172.20.0.0/16 skinsense_network

echo "✅ Network fixed! Ready for deployment."