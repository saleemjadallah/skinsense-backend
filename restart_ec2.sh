#!/bin/bash

echo "🔄 Restarting SkinSense backend on EC2..."

ssh -o StrictHostKeyChecking=no ${EC2_USER:-ubuntu}@${EC2_HOST:-56.228.12.81} << 'ENDSSH'
    cd /home/ubuntu/skinsense-backend
    
    echo "🛑 Stopping containers..."
    docker-compose down
    
    echo "🚀 Starting containers..."
    docker-compose up -d
    
    echo "⏳ Waiting for services to start..."
    sleep 10
    
    echo "📊 Container status:"
    docker-compose ps
    
    echo "📋 Checking logs..."
    docker-compose logs --tail=20 web
    
    echo "✅ Restart complete!"
ENDSSH

echo "✨ Done!"