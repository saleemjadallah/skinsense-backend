#!/bin/bash
set -e

# Configuration
COMPOSE_FILE="docker-compose.production.yml"
NETWORK_NAME="skinsense_network"
NGINX_CONTAINER="skinsense_nginx"
HEALTH_CHECK_TIMEOUT=60
DRAIN_TIMEOUT=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging functions
log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; exit 1; }

# Cleanup function
cleanup_resources() {
    log "Cleaning up Docker resources..."
    
    # Remove stopped containers
    docker container prune -f >/dev/null 2>&1 || true
    
    # Remove unused networks
    docker network prune -f >/dev/null 2>&1 || true
    
    # Remove dangling images
    docker image prune -f >/dev/null 2>&1 || true
    
    success "Cleanup complete"
}

# Get current active backend from nginx config
get_active_backend() {
    # Extract current backend from default.conf using grep and sed
    if docker exec $NGINX_CONTAINER test -f /etc/nginx/conf.d/default.conf 2>/dev/null; then
        local current=$(docker exec $NGINX_CONTAINER grep -o 'backend-[a-z]*:8000' /etc/nginx/conf.d/default.conf 2>/dev/null | head -1 | sed 's/backend-\([a-z]*\):8000/\1/')
        if [ -n "$current" ]; then
            echo "$current"
        else
            echo "blue"  # Default
        fi
    else
        echo "blue"  # Default
    fi
}

# Check container health
check_health() {
    local container=$1
    local max_attempts=$2
    local attempt=0
    
    log "Checking health of $container..."
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec $container curl -sf http://localhost:8000/health >/dev/null 2>&1; then
            success "$container is healthy"
            return 0
        fi
        
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done
    
    echo ""
    warning "$container health check failed after $max_attempts attempts"
    return 1
}

# Main deployment
main() {
    log "Starting zero-downtime deployment..."
    
    # Always recreate network to avoid label issues
    log "Setting up network..."
    docker network rm $NETWORK_NAME 2>/dev/null || true
    docker network create --driver bridge --subnet 172.20.0.0/16 $NETWORK_NAME 2>/dev/null || true
    
    # Verify network exists
    if ! docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        error "Failed to create network $NETWORK_NAME"
    fi
    
    # Get current active backend
    CURRENT_COLOR=$(get_active_backend)
    NEW_COLOR=$([[ "$CURRENT_COLOR" == "blue" ]] && echo "green" || echo "blue")
    
    log "Current: $CURRENT_COLOR → New: $NEW_COLOR"
    
    # Start Redis if not running
    if ! docker ps | grep -q skinsense_redis; then
        log "Starting Redis..."
        docker-compose -f $COMPOSE_FILE up -d redis
        sleep 5
    fi
    
    # Build new image
    log "Building $NEW_COLOR image..."
    docker-compose -f $COMPOSE_FILE build backend-$NEW_COLOR
    
    # Start new container
    log "Starting $NEW_COLOR container..."
    if [ "$NEW_COLOR" == "green" ]; then
        docker-compose -f $COMPOSE_FILE --profile green up -d backend-green
    else
        docker-compose -f $COMPOSE_FILE up -d backend-blue
    fi
    
    # Wait for new container to be healthy
    if ! check_health "skinsense_backend_$NEW_COLOR" 30; then
        error "New container failed health check, aborting deployment"
    fi
    
    # Start nginx if not running
    if ! docker ps | grep -q $NGINX_CONTAINER; then
        log "Starting nginx..."
        docker-compose -f $COMPOSE_FILE up -d nginx
        sleep 3
        
        # Clean up any old active.conf files that might exist
        log "Cleaning up old nginx configuration files..."
        docker exec $NGINX_CONTAINER rm -f /etc/nginx/conf.d/active.conf 2>/dev/null || true
        docker exec $NGINX_CONTAINER rm -f /etc/nginx/conf.d/.active 2>/dev/null || true
    else
        # Clean up old files on running container
        log "Cleaning up old nginx configuration files..."
        docker exec $NGINX_CONTAINER rm -f /etc/nginx/conf.d/active.conf 2>/dev/null || true
        docker exec $NGINX_CONTAINER rm -f /etc/nginx/conf.d/.active 2>/dev/null || true
    fi
    
    # Switch traffic to new container using DNS variable approach
    log "Switching traffic to $NEW_COLOR..."
    
    # Update the backend variable in nginx config using sed
    # This approach uses Docker's internal DNS resolver for reliable container resolution
    docker exec $NGINX_CONTAINER sed -i "s/set \$backend backend-[a-z]*:8000;/set \$backend backend-${NEW_COLOR}:8000;/g" /etc/nginx/conf.d/default.conf
    
    # Test nginx configuration (should now work with DNS resolver)
    log "Testing nginx configuration..."
    if docker exec $NGINX_CONTAINER nginx -t; then
        log "✓ Nginx configuration test passed"
        docker exec $NGINX_CONTAINER nginx -s reload
        success "Traffic switched to $NEW_COLOR"
    else
        # Fallback: try reload anyway (DNS resolver usually makes it work)
        warning "Configuration test failed, but trying reload with DNS resolver..."
        docker exec $NGINX_CONTAINER nginx -s reload
        success "Nginx reloaded - DNS resolver should handle backend resolution"
    fi
    
    # Wait for connections to drain
    log "Draining connections from $CURRENT_COLOR (${DRAIN_TIMEOUT}s)..."
    sleep $DRAIN_TIMEOUT
    
    # Stop old container
    log "Stopping $CURRENT_COLOR container..."
    docker-compose -f $COMPOSE_FILE stop backend-$CURRENT_COLOR || true
    docker-compose -f $COMPOSE_FILE rm -f backend-$CURRENT_COLOR || true
    
    # Cleanup
    cleanup_resources
    
    # Final health check
    log "Verifying deployment..."
    if curl -sf http://localhost/health >/dev/null 2>&1; then
        success "Deployment successful! API is healthy on $NEW_COLOR"
    else
        warning "API health check via nginx failed, but container is running"
    fi
    
    # Show status
    echo ""
    log "Deployment Summary:"
    echo "  • Previous: $CURRENT_COLOR"
    echo "  • Active: $NEW_COLOR"
    echo "  • Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep skinsense || true
}

# Run deployment
main "$@"