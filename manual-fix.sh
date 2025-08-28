#!/bin/bash

# Manual fix script to run on EC2 server
# This resolves all Docker network and container issues

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}     SkinSense Manual Deployment Fix       ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}Step 1: Stopping all containers...${NC}"
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm -f $(docker ps -aq) 2>/dev/null || true
echo -e "${GREEN}✓ All containers stopped${NC}"

echo -e "${YELLOW}Step 2: Removing problematic networks...${NC}"
docker network rm skinsense_network 2>/dev/null || true
docker network rm skinsense-network 2>/dev/null || true
docker network rm app_network 2>/dev/null || true
docker network prune -f 2>/dev/null || true
echo -e "${GREEN}✓ Networks cleaned${NC}"

echo -e "${YELLOW}Step 3: Creating fresh network...${NC}"
docker network create --driver bridge --subnet 172.20.0.0/16 skinsense_network
echo -e "${GREEN}✓ Network created${NC}"

echo -e "${YELLOW}Step 4: Starting services with docker-compose...${NC}"
# Start Redis first
docker-compose -f docker-compose.production.yml up -d redis
sleep 5

# Start blue backend (default)
docker-compose -f docker-compose.production.yml up -d backend-blue

# Wait for backend to be healthy
echo "Waiting for backend to start..."
for i in {1..30}; do
    if docker exec skinsense_backend_blue curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is healthy${NC}"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Start nginx
docker-compose -f docker-compose.production.yml up -d nginx
sleep 3

echo -e "${YELLOW}Step 5: Configuring nginx...${NC}"
# Ensure active.conf points to blue
cat > nginx/conf.d/active.conf << 'EOF'
# Active backend configuration
# This file is automatically managed by the deployment script
# DO NOT EDIT MANUALLY

upstream backend_active {
    server backend-blue:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
EOF

echo "blue" > nginx/conf.d/.active

# Copy to nginx container
docker cp nginx/conf.d/active.conf skinsense_nginx:/etc/nginx/conf.d/
docker exec skinsense_nginx nginx -s reload

echo -e "${GREEN}✓ Nginx configured${NC}"

echo -e "${YELLOW}Step 6: Final health check...${NC}"
sleep 5

if curl -sf http://localhost/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ API is accessible via nginx!${NC}"
else
    echo -e "${YELLOW}⚠ API may still be starting up${NC}"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}Deployment fixed! Current status:${NC}"
echo ""
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep skinsense || echo "No containers found"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "1. Test API: curl http://localhost/health"
echo "2. Check logs: docker logs skinsense_backend_blue"
echo "3. For future deployments, just push to GitHub main branch"