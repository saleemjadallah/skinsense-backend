#!/bin/bash

echo "======================================"
echo "🔧 FIXING 502 BAD GATEWAY ERROR"
echo "======================================"
echo ""

# Function to check if API is responding
check_api() {
    curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null
}

# 1. First, check current status
echo "📊 Current Status:"
echo "-----------------"
docker ps --format "table {{.Names}}\t{{.Status}}"
echo ""

# 2. Check if backend is running
PROJECT_NAME="skinsense-backend"
API_RUNNING=$(docker ps | grep -c "api" || true)

if [ "$API_RUNNING" -eq 0 ]; then
    echo "❌ Backend container not running. Starting it..."
    
    cd ~/skinsense-backend 2>/dev/null || {
        echo "❌ Backend directory not found!"
        echo "Creating from backup..."
        
        # Find most recent backup
        LATEST_BACKUP=$(ls -dt ~/skinsense-backend.backup.* 2>/dev/null | head -1)
        if [ ! -z "$LATEST_BACKUP" ]; then
            echo "Restoring from $LATEST_BACKUP"
            cp -r $LATEST_BACKUP ~/skinsense-backend
            cd ~/skinsense-backend
        else
            echo "❌ No backup found! Please redeploy."
            exit 1
        fi
    }
    
    # Start containers
    docker-compose -p $PROJECT_NAME up -d
    
    echo "⏳ Waiting for containers to start..."
    sleep 30
else
    echo "✅ Backend container is running"
fi

# 3. Check if API responds
echo ""
echo "🔍 Checking API health..."
HEALTH_STATUS=$(check_api)
if [ "$HEALTH_STATUS" = "200" ] || [ "$HEALTH_STATUS" = "503" ]; then
    echo "✅ API is responding (HTTP $HEALTH_STATUS)"
else
    echo "❌ API not responding (HTTP $HEALTH_STATUS)"
    echo "Checking logs..."
    docker logs $(docker ps --format "{{.Names}}" | grep api | head -1) --tail 50
    
    echo ""
    echo "🔄 Restarting API container..."
    docker restart $(docker ps --format "{{.Names}}" | grep api | head -1)
    sleep 20
fi

# 4. Setup nginx if not configured
echo ""
echo "🔧 Configuring Nginx..."

# Create nginx configuration for api.skinsense.app
sudo tee /etc/nginx/sites-available/skinsense-api << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name api.skinsense.app;

    # Increase timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    
    # Increase buffer sizes
    client_max_body_size 100M;
    client_body_buffer_size 100M;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Disable buffering for streaming
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/skinsense-api /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null

# Test nginx configuration
echo "Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    echo "Reloading nginx..."
    sudo systemctl reload nginx
else
    echo "❌ Nginx configuration error!"
    exit 1
fi

# 5. Setup SSL with Certbot (optional)
echo ""
echo "📜 SSL Certificate Setup:"
echo "------------------------"
if command -v certbot &> /dev/null; then
    echo "Certbot is installed."
    echo "To setup SSL, run:"
    echo "sudo certbot --nginx -d api.skinsense.app"
else
    echo "Certbot not installed. To install and setup SSL:"
    echo "sudo apt-get update"
    echo "sudo apt-get install certbot python3-certbot-nginx"
    echo "sudo certbot --nginx -d api.skinsense.app"
fi

# 6. Final checks
echo ""
echo "🎯 Final Verification:"
echo "---------------------"

# Check if nginx is running
if sudo systemctl is-active nginx > /dev/null; then
    echo "✅ Nginx is running"
else
    echo "❌ Nginx not running. Starting..."
    sudo systemctl start nginx
fi

# Check if API responds locally
FINAL_CHECK=$(check_api)
if [ "$FINAL_CHECK" = "200" ] || [ "$FINAL_CHECK" = "503" ]; then
    echo "✅ API responding on localhost:8000"
else
    echo "⚠️ API may still be starting up..."
fi

# Check docker containers
echo ""
echo "📦 Docker containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "======================================"
echo "✅ FIXES APPLIED"
echo "======================================"
echo ""
echo "Your API should now be accessible at:"
echo "http://api.skinsense.app"
echo ""
echo "If you still see 502 error:"
echo "1. Wait 1-2 minutes for services to fully start"
echo "2. Check DNS points to your EC2 IP"
echo "3. Ensure security group allows port 80/443"
echo "4. Run: docker logs skinsense-backend-api-1 --tail 100"
echo ""