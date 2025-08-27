#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

# Start deployment
print_status "🚀 Starting zero-downtime deployment for SkinSense AI Backend..."

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    print_error "Docker or Docker Compose is not installed!"
    exit 1
fi

# Use docker compose v2 if available, otherwise fall back to docker-compose
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# Navigate to the backend directory
cd "$(dirname "$0")"

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found! Please create it from .env.example"
    exit 1
fi

# Determine which color is currently active
ACTIVE_COLOR="blue"  # Default to blue

# Check if active backend file exists
if [ -f nginx/conf.d/active_backend ]; then
    ACTIVE_COLOR=$(cat nginx/conf.d/active_backend 2>/dev/null || echo "blue")
elif docker exec skinsense_nginx cat /etc/nginx/conf.d/active_backend 2>/dev/null; then
    ACTIVE_COLOR=$(docker exec skinsense_nginx cat /etc/nginx/conf.d/active_backend 2>/dev/null || echo "blue")
fi

# Determine new color
if [ "$ACTIVE_COLOR" = "green" ]; then
    NEW_COLOR="blue"
else
    NEW_COLOR="green"
fi

print_status "📦 Current active: $ACTIVE_COLOR, deploying to: $NEW_COLOR"

# Pull latest code if in git repository
if [ -d .git ]; then
    print_status "📥 Pulling latest code from repository..."
    git pull origin main || print_warning "Could not pull from git (may not be a git repo)"
fi

# Build new image
print_status "🔨 Building new Docker image for $NEW_COLOR..."
$COMPOSE_CMD -f docker-compose.blue-green.yml build backend-$NEW_COLOR

# Start the new container
print_status "🐳 Starting $NEW_COLOR container..."
if [ "$NEW_COLOR" = "green" ]; then
    $COMPOSE_CMD -f docker-compose.blue-green.yml --profile green up -d backend-green
else
    $COMPOSE_CMD -f docker-compose.blue-green.yml up -d backend-blue
fi

# Function to check health
check_health() {
    local color=$1
    local container_name="skinsense_backend_$color"
    
    # Try different methods to check health
    if docker exec $container_name curl -f http://localhost:8000/health > /dev/null 2>&1; then
        return 0
    elif docker exec $container_name wget -q --spider http://localhost:8000/health 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Wait for new container to be healthy
print_status "⏳ Waiting for $NEW_COLOR to be healthy..."
MAX_RETRIES=60
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if check_health $NEW_COLOR; then
        print_success "$NEW_COLOR is healthy!"
        break
    fi
    echo -n "."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

echo ""  # New line after dots

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    print_error "Health check failed for $NEW_COLOR after $MAX_RETRIES attempts"
    print_status "🔄 Rolling back..."
    $COMPOSE_CMD -f docker-compose.blue-green.yml stop backend-$NEW_COLOR
    if [ "$NEW_COLOR" = "green" ]; then
        $COMPOSE_CMD -f docker-compose.blue-green.yml --profile green rm -f backend-green
    else
        $COMPOSE_CMD -f docker-compose.blue-green.yml rm -f backend-blue
    fi
    exit 1
fi

# Update nginx configuration to route to new color
print_status "🔄 Switching traffic to $NEW_COLOR..."

# Create updated nginx configuration
cat > nginx/conf.d/active.conf <<EOF
# This file is dynamically updated during blue-green deployment
# DO NOT EDIT MANUALLY - Managed by deploy.sh script

# Currently active backend (updated at $(date))
upstream backend_active {
    server backend-$NEW_COLOR:8000 max_fails=3 fail_timeout=30s;
}
EOF

# Store active color
echo "$NEW_COLOR" > nginx/conf.d/active_backend

# Ensure nginx container is running
if ! docker ps | grep -q skinsense_nginx; then
    print_status "Starting nginx container..."
    $COMPOSE_CMD -f docker-compose.blue-green.yml up -d nginx
    sleep 5
fi

# Copy new configuration to nginx container and reload
docker cp nginx/conf.d/active.conf skinsense_nginx:/etc/nginx/conf.d/active.conf
docker exec skinsense_nginx sh -c "echo '$NEW_COLOR' > /etc/nginx/conf.d/active_backend"

# Test nginx configuration
print_status "Testing nginx configuration..."
if docker exec skinsense_nginx nginx -t; then
    print_success "Nginx configuration is valid"
else
    print_error "Nginx configuration test failed!"
    exit 1
fi

# Reload nginx without dropping connections
print_status "Reloading nginx configuration..."
docker exec skinsense_nginx nginx -s reload

print_success "Traffic switched to $NEW_COLOR"

# Wait for connections to drain from old container
print_status "⏰ Waiting for connections to drain from $ACTIVE_COLOR..."
sleep 15

# Stop the old container gracefully
print_status "🛑 Stopping $ACTIVE_COLOR container gracefully..."
$COMPOSE_CMD -f docker-compose.blue-green.yml stop backend-$ACTIVE_COLOR

# Remove old container
print_status "🗑️ Removing $ACTIVE_COLOR container..."
if [ "$ACTIVE_COLOR" = "green" ]; then
    $COMPOSE_CMD -f docker-compose.blue-green.yml --profile green rm -f backend-green
else
    $COMPOSE_CMD -f docker-compose.blue-green.yml rm -f backend-blue
fi

# Clean up old images (optional)
print_status "🧹 Cleaning up unused Docker resources..."
docker image prune -f > /dev/null 2>&1 || true

# Verify deployment
print_status "🔍 Verifying deployment..."
if check_health $NEW_COLOR; then
    print_success "Deployment verification successful!"
    
    # Show deployment summary
    echo ""
    print_status "📊 Deployment Summary:"
    echo -e "  • Previous version: ${YELLOW}$ACTIVE_COLOR${NC}"
    echo -e "  • New version: ${GREEN}$NEW_COLOR${NC}"
    echo -e "  • API Status: ${GREEN}Healthy${NC}"
    echo -e "  • Deployment time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    print_success "✨ Zero-downtime deployment complete! Now serving from $NEW_COLOR"
else
    print_error "Deployment verification failed!"
    exit 1
fi