#!/bin/bash

# Fix script for 502 Gateway Error on api.skinsense.app
# This script will restart the Docker containers and fix common issues

echo "🔧 SkinSense API 502 Error Fix Script"
echo "======================================"
echo "This will fix the 502 Gateway Error on api.skinsense.app"
echo ""

# Using the provided EC2 key path
EC2_KEY_PATH="/Users/saleemjadallah/Desktop/SkinSense(Dev)/skinsense.pem"

# EC2 details
EC2_HOST="56.228.12.81"
EC2_USER="ubuntu"

# Check if key exists
if [ ! -f "$EC2_KEY_PATH" ]; then
    echo "❌ EC2 key not found at: $EC2_KEY_PATH"
    exit 1
fi

echo "📡 Connecting to EC2..."

ssh -o StrictHostKeyChecking=no -i "$EC2_KEY_PATH" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
    echo "🔍 Diagnosing the issue..."
    
    # Check nginx status (if exists)
    if command -v nginx &> /dev/null; then
        echo "Nginx status:"
        sudo systemctl status nginx --no-pager | head -10
    fi
    
    # Check what's using port 8000
    echo ""
    echo "Checking port 8000:"
    sudo lsof -i:8000 || echo "Port 8000 is free"
    
    # Check Docker status
    echo ""
    echo "Docker containers:"
    docker ps -a
    
    # Navigate to project
    cd ~/skinsense-backend || {
        echo "❌ Project directory not found!"
        exit 1
    }
    
    # NUCLEAR FIX - Complete restart
    echo ""
    echo "🔥 Starting nuclear fix..."
    
    # 1. Stop everything
    echo "1️⃣ Stopping all containers..."
    docker-compose down -v 2>/dev/null || true
    docker stop $(docker ps -aq) 2>/dev/null || true
    docker rm -f $(docker ps -aq) 2>/dev/null || true
    
    # 2. Kill anything on port 8000
    echo "2️⃣ Freeing port 8000..."
    sudo fuser -k 8000/tcp 2>/dev/null || true
    sudo lsof -ti:8000 | xargs -r sudo kill -9 2>/dev/null || true
    
    # 3. Clean Docker completely
    echo "3️⃣ Cleaning Docker..."
    docker system prune -af --volumes
    docker network prune -f
    
    # 4. Verify .env exists and has required vars
    echo "4️⃣ Checking environment variables..."
    if [ -f .env ]; then
        echo "✅ .env file exists"
        
        # Check for critical variables
        if grep -q "MONGODB_URL=" .env && grep -q "SECRET_KEY=" .env; then
            echo "✅ Critical environment variables found"
        else
            echo "⚠️  Warning: Some environment variables may be missing"
        fi
    else
        echo "❌ .env file is missing! API will not work!"
        echo "Please ensure deployment includes .env file"
        exit 1
    fi
    
    # 5. Rebuild everything fresh
    echo "5️⃣ Building fresh Docker images..."
    docker-compose build --no-cache
    
    # 6. Start with specific project name
    echo "6️⃣ Starting containers..."
    docker-compose up -d --force-recreate --remove-orphans
    
    # 7. Wait for startup
    echo "7️⃣ Waiting for services to start..."
    sleep 20
    
    # 8. Check if containers are running
    echo "8️⃣ Checking container status..."
    RUNNING_CONTAINERS=$(docker ps --format "{{.Names}}")
    
    if echo "$RUNNING_CONTAINERS" | grep -q "api"; then
        echo "✅ API container is running"
    else
        echo "❌ API container is NOT running"
        echo "Checking logs:"
        docker-compose logs api --tail=50
    fi
    
    if echo "$RUNNING_CONTAINERS" | grep -q "redis"; then
        echo "✅ Redis container is running"
    else
        echo "❌ Redis container is NOT running"
    fi
    
    # 9. Test the API
    echo "9️⃣ Testing API health..."
    MAX_ATTEMPTS=15
    SUCCESS=false
    
    for i in $(seq 1 $MAX_ATTEMPTS); do
        echo "Health check attempt $i/$MAX_ATTEMPTS..."
        
        if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ API is responding on port 8000!"
            SUCCESS=true
            
            # Show the actual response
            echo "Health response:"
            curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
            break
        else
            if [ "$i" -lt "$MAX_ATTEMPTS" ]; then
                echo "Not ready yet, waiting 5 seconds..."
                sleep 5
            fi
        fi
    done
    
    # 10. Restart nginx if needed
    if command -v nginx &> /dev/null; then
        echo "🔟 Restarting nginx..."
        sudo systemctl restart nginx
        sleep 2
        sudo systemctl status nginx --no-pager | head -5
    fi
    
    # Final status report
    echo ""
    echo "==================================="
    echo "📊 FINAL STATUS REPORT"
    echo "==================================="
    
    if [ "$SUCCESS" = true ]; then
        echo "✅ API is running and healthy!"
        echo ""
        echo "Internal endpoints:"
        echo "- Health: http://localhost:8000/health"
        echo "- Docs: http://localhost:8000/docs"
        echo ""
        echo "External endpoints:"
        echo "- API: http://56.228.12.81:8000"
        echo "- Via Domain: https://api.skinsense.app"
    else
        echo "❌ API is not responding properly"
        echo ""
        echo "Troubleshooting steps:"
        echo "1. Check Docker logs: docker-compose logs api"
        echo "2. Check if MongoDB connection string is correct in .env"
        echo "3. Check if all required environment variables are set"
        echo "4. Try rebuilding: docker-compose build --no-cache"
        
        echo ""
        echo "Current container status:"
        docker ps -a
        
        echo ""
        echo "Last 30 lines of API logs:"
        docker-compose logs api --tail=30
    fi
ENDSSH

echo ""
echo "🏁 Fix script complete!"