#!/bin/bash

# Emergency cleanup script for deployment issues
# USE WITH CAUTION - This will stop and remove all SkinSense containers

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}⚠️  Emergency Cleanup Script${NC}"
echo "This will stop and remove all SkinSense containers and networks."
read -p "Are you sure? (yes/no): " -r
echo

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo -e "${RED}Stopping all SkinSense containers...${NC}"

# Stop all containers
docker stop skinsense_nginx 2>/dev/null || true
docker stop skinsense_backend_blue 2>/dev/null || true
docker stop skinsense_backend_green 2>/dev/null || true
docker stop skinsense_redis 2>/dev/null || true

echo "Removing containers..."

# Remove containers
docker rm -f skinsense_nginx 2>/dev/null || true
docker rm -f skinsense_backend_blue 2>/dev/null || true
docker rm -f skinsense_backend_green 2>/dev/null || true
docker rm -f skinsense_redis 2>/dev/null || true

echo "Removing networks..."

# Remove all possible network names
docker network rm skinsense_network 2>/dev/null || true
docker network rm skinsense-network 2>/dev/null || true
docker network rm app_network 2>/dev/null || true

echo "Cleaning up volumes..."

# Remove volumes (optional - uncomment if needed)
# docker volume rm skinsense_redis_data 2>/dev/null || true

echo "Cleaning up dangling resources..."

# Clean up dangling images and containers
docker container prune -f
docker image prune -f
docker network prune -f

echo "Creating fresh network..."
docker network create --driver bridge --subnet 172.20.0.0/16 skinsense_network 2>/dev/null || true

echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""
echo "To redeploy, run:"
echo "  ./deploy.sh"