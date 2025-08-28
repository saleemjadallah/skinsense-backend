#!/bin/bash

# Status check script for SkinSense deployment

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}     SkinSense Deployment Status Check     ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo ""

# Check active backend
echo -e "${YELLOW}Active Backend:${NC}"
if [ -f nginx/conf.d/.active ]; then
    ACTIVE=$(cat nginx/conf.d/.active)
    echo -e "  ${GREEN}→ $ACTIVE${NC}"
else
    echo -e "  ${RED}→ Unknown${NC}"
fi
echo ""

# Check containers
echo -e "${YELLOW}Container Status:${NC}"
for container in skinsense_nginx skinsense_backend_blue skinsense_backend_green skinsense_redis; do
    if docker ps | grep -q $container; then
        echo -e "  ${GREEN}✓${NC} $container - Running"
    else
        echo -e "  ${RED}✗${NC} $container - Not running"
    fi
done
echo ""

# Check health endpoints
echo -e "${YELLOW}Health Checks:${NC}"

# Check nginx
if curl -sf http://localhost/nginx-status >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Nginx - Healthy"
else
    echo -e "  ${RED}✗${NC} Nginx - Unhealthy"
fi

# Check API via nginx
if curl -sf http://localhost/health >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} API (via nginx) - Healthy"
else
    echo -e "  ${RED}✗${NC} API (via nginx) - Unhealthy"
fi

# Check direct API access
for color in blue green; do
    if docker exec skinsense_backend_$color curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} Backend $color - Healthy"
    else
        echo -e "  ${RED}✗${NC} Backend $color - Not available"
    fi
done
echo ""

# Check network
echo -e "${YELLOW}Network Status:${NC}"
if docker network inspect skinsense_network >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} skinsense_network exists"
    # Count connected containers
    CONNECTED=$(docker network inspect skinsense_network -f '{{len .Containers}}' 2>/dev/null || echo "0")
    echo -e "  → $CONNECTED containers connected"
else
    echo -e "  ${RED}✗${NC} skinsense_network not found"
fi
echo ""

# Show running containers
echo -e "${YELLOW}Running Containers:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep skinsense || echo "  None found"
echo ""

echo -e "${BLUE}═══════════════════════════════════════════${NC}"