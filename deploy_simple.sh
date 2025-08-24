#!/bin/bash

# Simple deployment script to run directly on EC2
# This avoids Docker Compose version issues

echo "🚀 Starting simple deployment..."

# Navigate to backend directory
cd ~/skinsense-backend || exit 1

# Stop all containers
echo "📦 Stopping existing containers..."
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true

# Clean up
echo "🧹 Cleaning up..."
docker system prune -af --volumes

# Build the API image
echo "🔨 Building Docker image..."
docker build -t skinsense-api:latest .

# Start Redis
echo "🚀 Starting Redis..."
docker run -d \
  --name redis \
  --restart always \
  -p 6379:6379 \
  redis:7-alpine

# Start the API
echo "🚀 Starting API..."
docker run -d \
  --name api \
  --restart always \
  -p 8000:8000 \
  --link redis:redis \
  -e REDIS_URL=redis://redis:6379 \
  --env-file .env \
  skinsense-api:latest

# Wait for services
sleep 5

# Check status
echo "✅ Checking services..."
docker ps

# Health check
echo "🏥 Running health check..."
curl -f http://localhost:8000/health || echo "⚠️ Health check failed"

echo "✅ Deployment complete!"
echo "📚 API: http://$(curl -s ifconfig.me):8000"
echo "📚 Docs: http://$(curl -s ifconfig.me):8000/docs"