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

# Get current active backend
get_active_backend() {
    if [ -f "nginx/conf.d/.active" ]; then
        cat nginx/conf.d/.active
    elif docker exec $NGINX_CONTAINER test -f /etc/nginx/conf.d/.active 2>/dev/null; then
        docker exec $NGINX_CONTAINER cat /etc/nginx/conf.d/.active 2>/dev/null
    else
        echo "blue"  # Default
    fi
}

# Set active backend
set_active_backend() {
    local color=$1
    echo "$color" > nginx/conf.d/.active
    
    # Update nginx configuration
    cat > nginx/conf.d/active.conf << EOF
# Active backend configuration
# Updated at $(date)
# DO NOT EDIT MANUALLY

upstream backend_active {
    server backend-${color}:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}
EOF
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
    
    # Check if system restart is required
    if [ -f /var/run/reboot-required ]; then
        warning "System restart is required after package updates"
        warning "Consider scheduling a maintenance window to restart the server"
    fi
    
    # Set up network with better error handling
    log "Setting up network..."
    
    # Check if network already exists
    if docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        log "Network $NETWORK_NAME already exists, checking if it's healthy..."
        # Test network connectivity
        if docker run --rm --network $NETWORK_NAME alpine:latest ping -c 1 8.8.8.8 >/dev/null 2>&1; then
            log "Network is healthy, reusing existing network"
        else
            warning "Network exists but seems unhealthy, recreating..."
            docker network rm $NETWORK_NAME 2>/dev/null || true
            docker network create --driver bridge --subnet 172.20.0.0/16 $NETWORK_NAME
        fi
    else
        log "Creating new network..."
        docker network create --driver bridge --subnet 172.20.0.0/16 $NETWORK_NAME
    fi
    
    # Verify network exists and is working
    if ! docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        error "Failed to create or verify network $NETWORK_NAME"
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
        sleep 5
        
        # Wait for nginx to be fully ready
        for i in {1..10}; do
            if docker exec $NGINX_CONTAINER nginx -t >/dev/null 2>&1; then
                break
            fi
            log "Waiting for nginx to be ready... ($i/10)"
            sleep 2
        done
    fi
    
    # Verify new backend is reachable from nginx container
    log "Verifying backend connectivity..."
    if ! docker exec $NGINX_CONTAINER curl -sf http://backend-${NEW_COLOR}:8000/health >/dev/null 2>&1; then
        error "Cannot reach backend-${NEW_COLOR} from nginx container"
    fi
    
    # Switch traffic to new container
    log "Switching traffic to $NEW_COLOR..."
    
    # Create temporary nginx config file
    cat > /tmp/nginx-config.conf << EOF
server {
    listen 80 default_server;
    server_name _;
    
    # Add timeout settings for better reliability
    proxy_connect_timeout 10s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;
    
    location / {
        proxy_pass http://backend-${NEW_COLOR}:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Add upstream health check
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
        proxy_next_upstream_tries 3;
    }
    
    location /health {
        access_log off;
        proxy_pass http://backend-${NEW_COLOR}:8000/health;
        proxy_connect_timeout 5s;
        proxy_read_timeout 5s;
    }
}
EOF
    
    # Config created, ready to copy to container
    
    # Copy config to nginx container
    if docker cp /tmp/nginx-config.conf $NGINX_CONTAINER:/etc/nginx/conf.d/default.conf; then
        success "Nginx configuration updated"
    else
        error "Failed to copy nginx configuration"
    fi
    rm -f /tmp/nginx-config.conf
    
    # Test and reload nginx
    log "Testing nginx configuration..."
    if docker exec $NGINX_CONTAINER nginx -t; then
        log "Nginx config test passed, reloading..."
        if docker exec $NGINX_CONTAINER nginx -s reload; then
            success "Traffic switched to $NEW_COLOR"
        else
            error "Nginx reload failed"
        fi
    else
        error "Nginx configuration test failed"
        log "Debugging nginx configuration..."
        docker exec $NGINX_CONTAINER cat /etc/nginx/conf.d/default.conf || true
        docker exec $NGINX_CONTAINER nginx -T || true
        exit 1
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