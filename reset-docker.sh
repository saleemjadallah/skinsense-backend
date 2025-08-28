#!/bin/bash

# Complete Docker reset for deployment issues
# This script aggressively cleans all Docker resources

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}⚠️  COMPLETE DOCKER RESET${NC}"
echo "This will stop ALL containers and remove ALL networks"
echo ""

# Stop ALL containers
echo "Stopping all containers..."
docker stop $(docker ps -aq) 2>/dev/null || true

# Remove ALL containers
echo "Removing all containers..."
docker rm -f $(docker ps -aq) 2>/dev/null || true

# Remove ALL networks except default ones
echo "Removing all custom networks..."
docker network ls --format '{{.Name}}' | grep -v '^bridge$\|^host$\|^none$' | xargs -r docker network rm 2>/dev/null || true

# Clean up volumes
echo "Cleaning up volumes..."
docker volume prune -f 2>/dev/null || true

# Clean up images
echo "Cleaning up dangling images..."
docker image prune -f 2>/dev/null || true

# System prune
echo "Running system prune..."
docker system prune -f --volumes 2>/dev/null || true

echo -e "${GREEN}✓ Docker environment reset complete${NC}"
echo ""
echo "Now run: ./deploy.sh"