#!/bin/bash

# Test deployment health checks
echo "🔍 Testing deployment health checks..."
echo ""

# Test direct backend health (should fail if not exposed)
echo "1. Testing direct backend (port 8000):"
curl -sf http://localhost:8000/health >/dev/null 2>&1 && echo "✅ Backend directly accessible" || echo "❌ Backend not directly accessible (expected)"
echo ""

# Test nginx proxy health
echo "2. Testing nginx proxy (port 8080):"
if curl -sf http://localhost:8080/health >/dev/null 2>&1; then
    echo "✅ Health check successful via nginx!"
    echo "   Response:"
    curl -s http://localhost:8080/health | head -5
else
    echo "❌ Health check failed via nginx"
fi
echo ""

# Test nginx status
echo "3. Testing nginx status endpoint:"
if curl -sf http://localhost:8080/nginx-status >/dev/null 2>&1; then
    echo "✅ Nginx status endpoint working"
else
    echo "❌ Nginx status endpoint not accessible"
fi
echo ""

# Check running containers
echo "4. Docker containers status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep skinsense || echo "❌ No skinsense containers running"
echo ""

# Check for old blue-green containers
echo "5. Checking for old blue-green containers:"
old_containers=$(docker ps -a --format "{{.Names}}" | grep -E "skinsense_backend_(blue|green)" | wc -l)
if [ "$old_containers" -eq 0 ]; then
    echo "✅ No old blue-green containers found"
else
    echo "⚠️  Found $old_containers old blue-green containers"
    docker ps -a --format "table {{.Names}}\t{{.Status}}" | grep -E "skinsense_backend_(blue|green)"
fi