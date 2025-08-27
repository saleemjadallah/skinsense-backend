#!/bin/bash

# Manual restart script for SkinSense API
# Use this when GitHub Actions deployment has issues

echo "🔧 Manual SkinSense API Restart Script"
echo "======================================="

# EC2 connection details
EC2_HOST="56.228.12.81"
EC2_USER="ubuntu"
EC2_KEY_PATH="$HOME/.ssh/your-ec2-key.pem"  # Update this path

# Check if key exists
if [ ! -f "$EC2_KEY_PATH" ]; then
    echo "❌ EC2 key not found at: $EC2_KEY_PATH"
    echo "Please update the EC2_KEY_PATH in this script"
    exit 1
fi

echo "📡 Connecting to EC2 at $EC2_HOST..."

ssh -o StrictHostKeyChecking=no -i "$EC2_KEY_PATH" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
    echo "🔍 Checking current Docker status..."
    
    # Show current containers
    echo "Current containers:"
    docker ps -a
    
    # Navigate to project directory
    cd ~/skinsense-backend || {
        echo "❌ Project directory not found"
        echo "Creating project directory..."
        mkdir -p ~/skinsense-backend
        cd ~/skinsense-backend
    }
    
    # Check if docker-compose.yml exists
    if [ ! -f docker-compose.yml ]; then
        echo "❌ docker-compose.yml not found"
        echo "You need to deploy the project first"
        exit 1
    fi
    
    echo "🛑 Stopping all existing containers..."
    # Stop everything
    docker stop $(docker ps -aq) 2>/dev/null || true
    docker rm -f $(docker ps -aq) 2>/dev/null || true
    
    # Clean up networks
    echo "🧹 Cleaning up networks..."
    docker network rm $(docker network ls -q | grep -v bridge | grep -v host | grep -v none) 2>/dev/null || true
    docker network prune -f 2>/dev/null || true
    
    # Clean up system
    echo "🧹 Cleaning Docker system..."
    docker system prune -af --volumes 2>/dev/null || true
    
    # Check if .env file exists
    if [ ! -f .env ]; then
        echo "⚠️  Warning: .env file not found"
        echo "API may not work properly without environment variables"
    else
        echo "✅ .env file found"
    fi
    
    # Build fresh images
    echo "🏗️  Building Docker images..."
    docker-compose build --no-cache
    
    # Start containers
    echo "🚀 Starting containers..."
    docker-compose up -d --force-recreate --remove-orphans
    
    # Wait for services
    echo "⏳ Waiting for services to start (30 seconds)..."
    sleep 30
    
    # Check container status
    echo "📊 Container status:"
    docker-compose ps
    
    # Check logs
    echo "📝 Recent API logs:"
    docker-compose logs api --tail=20
    
    # Health check
    echo "🏥 Performing health check..."
    for i in {1..10}; do
        echo "Attempt $i/10..."
        if curl -f http://localhost:8000/health 2>/dev/null; then
            echo ""
            echo "✅ API is responding!"
            break
        else
            echo "Waiting 5 seconds..."
            sleep 5
        fi
    done
    
    # Final status
    echo ""
    echo "📊 Final container status:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # Test from inside the server
    echo ""
    echo "🧪 Testing API endpoints:"
    echo "Health check:"
    curl -s http://localhost:8000/health | python3 -m json.tool || echo "Failed"
    
    echo ""
    echo "API Docs should be available at:"
    echo "http://$EC2_HOST:8000/docs"
ENDSSH

echo ""
echo "🏁 Manual restart complete!"
echo "API should be available at: http://$EC2_HOST:8000"
echo "Documentation: http://$EC2_HOST:8000/docs"