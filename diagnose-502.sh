#!/bin/bash

echo "======================================"
echo "🔍 DIAGNOSING 502 BAD GATEWAY ERROR"
echo "======================================"
echo ""

# 1. Check if Docker containers are running
echo "1️⃣ CHECKING DOCKER CONTAINERS:"
echo "--------------------------------"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# 2. Check if port 8000 is listening
echo "2️⃣ CHECKING PORT 8000:"
echo "----------------------"
sudo netstat -tlnp | grep :8000 || echo "❌ Port 8000 is not listening!"
echo ""

# 3. Check if the API responds locally
echo "3️⃣ TESTING API LOCALLY:"
echo "-----------------------"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8000/health || echo "❌ API not responding on localhost:8000"
echo ""

# 4. Check Docker logs for the API container
echo "4️⃣ RECENT API CONTAINER LOGS:"
echo "------------------------------"
API_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "api|backend" | head -1)
if [ ! -z "$API_CONTAINER" ]; then
    echo "Container: $API_CONTAINER"
    docker logs $API_CONTAINER --tail 20 2>&1
else
    echo "❌ No API container found running!"
fi
echo ""

# 5. Check nginx configuration
echo "5️⃣ CHECKING NGINX:"
echo "------------------"
if command -v nginx &> /dev/null; then
    echo "Nginx installed: ✅"
    sudo nginx -t 2>&1
    echo ""
    echo "Nginx status:"
    sudo systemctl status nginx --no-pager | head -10
else
    echo "⚠️ Nginx not installed on system (might be in Docker)"
fi
echo ""

# 6. Check nginx container if exists
echo "6️⃣ CHECKING NGINX CONTAINER:"
echo "----------------------------"
NGINX_CONTAINER=$(docker ps --format "{{.Names}}" | grep nginx | head -1)
if [ ! -z "$NGINX_CONTAINER" ]; then
    echo "Nginx container: $NGINX_CONTAINER"
    docker logs $NGINX_CONTAINER --tail 10 2>&1
else
    echo "ℹ️ No nginx container running (using system nginx)"
fi
echo ""

# 7. Check if there's a reverse proxy configuration
echo "7️⃣ CHECKING REVERSE PROXY CONFIG:"
echo "---------------------------------"
if [ -f /etc/nginx/sites-enabled/default ]; then
    echo "System nginx config:"
    grep -E "proxy_pass|upstream|server_name" /etc/nginx/sites-enabled/default | head -10
elif [ -f /etc/nginx/nginx.conf ]; then
    echo "System nginx.conf:"
    grep -E "proxy_pass|upstream|server_name" /etc/nginx/nginx.conf | head -10
else
    echo "⚠️ No nginx configuration found in standard locations"
fi
echo ""

# 8. Check Docker network
echo "8️⃣ CHECKING DOCKER NETWORKS:"
echo "----------------------------"
docker network ls
echo ""

# 9. Test connectivity between containers
echo "9️⃣ TESTING CONTAINER CONNECTIVITY:"
echo "----------------------------------"
API_CONTAINER=$(docker ps --format "{{.Names}}" | grep -E "api|backend" | head -1)
if [ ! -z "$API_CONTAINER" ]; then
    echo "Testing if API container can be reached..."
    docker exec $API_CONTAINER curl -s http://localhost:8000/health || echo "❌ API not responding inside container"
else
    echo "❌ No API container to test"
fi
echo ""

# 10. Check memory and disk
echo "🔟 SYSTEM RESOURCES:"
echo "-------------------"
echo "Memory usage:"
free -h
echo ""
echo "Disk usage:"
df -h | grep -E "^/dev|Filesystem"
echo ""

# Summary
echo "======================================"
echo "📊 DIAGNOSIS SUMMARY:"
echo "======================================"
echo ""
echo "Possible causes of 502 error:"
echo "1. Backend container not running"
echo "2. Backend crashed due to errors"
echo "3. Port 8000 not accessible"
echo "4. Nginx misconfiguration"
echo "5. Network connectivity issues"
echo ""
echo "Run this script on your EC2 instance to identify the issue."