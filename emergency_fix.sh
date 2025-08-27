#!/bin/bash

echo "🚨 Emergency API Fix Script"
echo "=========================="

# SSH to EC2 and redeploy
ssh -o StrictHostKeyChecking=no -i "/Users/saleemjadallah/Desktop/SkinSense(Dev)/skinsense.pem" ubuntu@56.228.12.81 << 'EOF'
cd ~/skinsense-backend

echo "Current directory contents:"
ls -la

echo "Stopping any running containers..."
docker-compose down -v 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm -f $(docker ps -aq) 2>/dev/null || true

echo "Starting fresh deployment..."
docker-compose up -d --build

echo "Waiting for API to start (30 seconds)..."
sleep 30

echo "Container status:"
docker ps

echo "Testing API health:"
for i in {1..10}; do
    if curl -f -s http://localhost:8000/health; then
        echo ""
        echo "✅ API is working!"
        break
    else
        echo "Attempt $i/10 - waiting 5 seconds..."
        sleep 5
    fi
done

echo "Final status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
EOF

echo "Done! Check https://api.skinsense.app"