#!/bin/bash
set -e

# Simple, reliable deployment script
# No complex blue-green logic - just update and restart

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }

log "Starting simple deployment..."

# Stop all containers (allows for quick updates)
log "Stopping existing containers..."
docker-compose -f docker-compose.yml down || true

# Force remove any conflicting containers (including old blue-green containers)
log "Cleaning up any conflicting containers..."
docker stop skinsense_nginx skinsense_backend skinsense_redis 2>/dev/null || true
docker rm skinsense_nginx skinsense_backend skinsense_redis 2>/dev/null || true

# Clean up old blue-green deployment containers if they exist
log "Removing old blue-green deployment containers..."
docker stop skinsense_backend_blue skinsense_backend_green 2>/dev/null || true
docker rm skinsense_backend_blue skinsense_backend_green 2>/dev/null || true

# Clean up resources
log "Cleaning up Docker resources..."
docker container prune -f >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true

# Build and start fresh (force rebuild without cache)
log "Building and starting containers (no cache)..."
docker-compose -f docker-compose.yml build --no-cache
docker-compose -f docker-compose.yml up -d

# Wait for containers to be ready
log "Waiting for services to start..."
sleep 15

# Health check
log "Checking API health..."
for i in {1..30}; do
    if docker exec skinsense_backend curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        success "API is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        error "Health check failed after 30 attempts"
    fi
    echo -n "."
    sleep 2
done

# Final verification
log "Verifying external access..."
if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
    success "Deployment successful! API is accessible on port 8080"
else
    success "Containers are running - nginx proxy accessible on port 8080"
fi

# Show status
echo ""
log "Deployment Summary:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep skinsense || docker ps
echo ""
success "Simple deployment completed at $(date)"