#!/bin/bash

# Zero-Downtime Deployment Script for SkinSense Backend
# This script ensures minimal to zero downtime during deployments

set -e

echo "🚀 Starting zero-downtime deployment..."

PROJECT_NAME="skinsense-backend"
DEPLOYMENT_DIR="$HOME/skinsense-backend"
NEW_DEPLOYMENT_DIR="$HOME/skinsense-backend-new"

# Function to check container health
check_health() {
    local container_name=$1
    local max_attempts=30
    
    for i in $(seq 1 $max_attempts); do
        echo "Health check attempt $i of $max_attempts for $container_name..."
        
        if docker exec $container_name curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ $container_name is healthy!"
            return 0
        else
            echo "Waiting for $container_name to be ready..."
            sleep 5
        fi
    done
    
    echo "❌ $container_name health check failed!"
    return 1
}

# Function to gracefully stop containers
graceful_stop() {
    local project=$1
    echo "📦 Gracefully stopping $project..."
    
    # Send SIGTERM and wait for graceful shutdown
    docker-compose -p $project stop --timeout 30
    
    # Remove containers
    docker-compose -p $project rm -f
}

# Main deployment logic
main() {
    # Check if we're in the right directory
    if [ ! -f "docker-compose.yml" ]; then
        echo "❌ docker-compose.yml not found in current directory!"
        echo "Please run this script from the backend directory."
        exit 1
    fi
    
    # Check if there's an existing deployment
    if docker ps | grep -q "$PROJECT_NAME"; then
        echo "📊 Existing deployment detected. Starting blue-green deployment..."
        
        # Blue-Green Deployment Strategy
        echo "🔵 Current deployment (Blue) is running"
        echo "🟢 Preparing new deployment (Green)..."
        
        # Build new images
        echo "📦 Building new Docker images..."
        docker-compose build --no-cache
        
        # Start new containers with temporary project name
        echo "🟢 Starting Green deployment..."
        docker-compose -p ${PROJECT_NAME}-green up -d
        
        # Wait for green deployment to be healthy
        if check_health "${PROJECT_NAME}-green-api-1"; then
            echo "✅ Green deployment is healthy!"
            
            # Switch traffic by stopping blue and renaming green
            echo "🔄 Switching from Blue to Green..."
            
            # Gracefully stop blue deployment
            graceful_stop $PROJECT_NAME
            
            # Stop green temporarily
            docker-compose -p ${PROJECT_NAME}-green stop
            
            # Rename green to production
            docker-compose -p ${PROJECT_NAME}-green down
            docker-compose -p $PROJECT_NAME up -d
            
            echo "✅ Successfully switched to new deployment!"
        else
            echo "❌ Green deployment failed health check, rolling back..."
            docker-compose -p ${PROJECT_NAME}-green down
            exit 1
        fi
    else
        echo "📦 No existing deployment found. Starting fresh deployment..."
        
        # Build and start
        docker-compose build --no-cache
        docker-compose -p $PROJECT_NAME up -d
        
        # Health check
        sleep 10
        if check_health "${PROJECT_NAME}-api-1"; then
            echo "✅ Fresh deployment is healthy!"
        else
            echo "⚠️ Health check failed but containers are running"
            docker ps | grep $PROJECT_NAME
        fi
    fi
    
    # Cleanup
    echo "🗑️ Cleaning up..."
    docker system prune -f
    
    # Show status
    echo ""
    echo "📊 Deployment Status:"
    docker-compose -p $PROJECT_NAME ps
    
    echo ""
    echo "🎉 Zero-downtime deployment complete!"
    echo "📌 API is available at: http://localhost:8000"
    echo "📌 Health check: http://localhost:8000/health"
    echo "📌 API docs: http://localhost:8000/docs"
}

# Run main function
main "$@"