#!/bin/bash

echo "🔄 Restarting SkinSense backend on EC2..."

ssh -o StrictHostKeyChecking=no ${EC2_USER:-ubuntu}@${EC2_HOST:-56.228.12.81} << 'ENDSSH'
    cd /home/ubuntu/skinsense-backend
    
    echo "🔎 Determining current project name..."
    if [ -f ~/.current_project_name ]; then
        PROJECT_NAME=$(cat ~/.current_project_name)
        echo "Using stored project name: $PROJECT_NAME"
    else
        PROJECT_NAME="skinsense-backend"
        echo "No stored project name found. Using default: $PROJECT_NAME"
    fi

    echo "🛑 Stopping containers..."
    docker-compose -p "$PROJECT_NAME" down --remove-orphans || true
    docker network rm skinsense-backend_app_network 2>/dev/null || true
    docker network rm skinsense-backend_default 2>/dev/null || true
    
    echo "🚀 Starting containers..."
    docker-compose -p "$PROJECT_NAME" up -d --force-recreate --remove-orphans
    
    echo "⏳ Waiting for services to start..."
    sleep 10
    
    echo "📊 Container status:"
    docker-compose -p "$PROJECT_NAME" ps
    
    echo "📋 Checking logs..."
    docker-compose -p "$PROJECT_NAME" logs --tail=20
    
    echo "✅ Restart complete!"
ENDSSH

echo "✨ Done!"