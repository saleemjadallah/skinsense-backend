#!/bin/bash

# Force rebuild script for EC2 deployment
# This ensures Docker doesn't use cached layers

echo "🔄 Force Rebuild and Deploy to EC2"
echo "===================================="

# Get EC2 details from user or environment
EC2_HOST="${EC2_HOST:-}"
EC2_USER="${EC2_USER:-ubuntu}"
PEM_FILE="/Users/saleemjadallah/Desktop/SkinSense(Dev)/skinsense.pem"

# Try to find EC2 host from GitHub secrets or ask user
if [ -z "$EC2_HOST" ]; then
    echo "Please enter your EC2 host IP address:"
    read -r EC2_HOST
fi

echo "📦 Creating deployment package with cache-busting..."

# Create deployment directory
rm -rf deployment-force
mkdir -p deployment-force

# Copy all necessary files
cp -r app deployment-force/
cp requirements.txt deployment-force/
cp Dockerfile deployment-force/
cp docker-compose.simple.yml deployment-force/docker-compose.yml
cp -r nginx deployment-force/
cp deploy-simple.sh deployment-force/deploy.sh
cp docker-entrypoint.sh deployment-force/

# Create a modified deployment script that forces rebuild
cat > deployment-force/force-deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting FORCED rebuild deployment..."
echo "========================================="

# Stop and remove ALL containers
echo "1️⃣ Stopping all containers..."
docker-compose down -v || true
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true

# Remove the backend image to force rebuild
echo "2️⃣ Removing cached images..."
docker rmi skinsense-backend_backend 2>/dev/null || true
docker rmi $(docker images -q skinsense*) 2>/dev/null || true

# Clean Docker build cache
echo "3️⃣ Cleaning Docker build cache..."
docker builder prune -f || true
docker system prune -f || true

# Build with no cache
echo "4️⃣ Building fresh image (NO CACHE)..."
docker-compose build --no-cache backend

# Start services
echo "5️⃣ Starting services..."
docker-compose up -d

# Wait for services
echo "6️⃣ Waiting for services to be healthy..."
sleep 20

# Health check
echo "7️⃣ Checking health..."
for i in {1..30}; do
    if docker exec skinsense_backend curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo "✅ API is healthy!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Health check failed"
        docker logs skinsense_backend --tail 50
        exit 1
    fi
    echo -n "."
    sleep 2
done

# Verify the new code is deployed
echo ""
echo "8️⃣ Verifying deployment..."
echo "Checking for sync_achievements_from_existing_data method:"
docker exec skinsense_backend grep -n "sync_achievements_from_existing_data" /app/app/services/achievement_service.py | head -3 || echo "Method not found!"

echo "Checking for track_skin_analysis_completion calls:"
docker exec skinsense_backend grep -n "track_skin_analysis_completion" /app/app/api/v1/skin_analysis.py | head -3 || echo "Tracking not found!"

echo ""
echo "✅ Force rebuild complete!"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep skinsense
EOF

chmod +x deployment-force/force-deploy.sh

# Copy .env file from GitHub Actions secrets (you'll need to create this)
cat > deployment-force/.env << EOF
# Add your environment variables here
# Copy from your .env or GitHub secrets
EOF

# Create archive
tar -czf deployment-force.tar.gz -C deployment-force .

echo ""
echo "📤 Uploading to EC2..."
scp -i "$PEM_FILE" deployment-force.tar.gz "$EC2_USER@$EC2_HOST:/tmp/"

echo ""
echo "🔨 Running force rebuild on EC2..."
ssh -i "$PEM_FILE" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
set -e

# Go to project directory
cd ~/skinsense-backend || mkdir -p ~/skinsense-backend
cd ~/skinsense-backend

# Extract new deployment
echo "Extracting deployment package..."
tar -xzf /tmp/deployment-force.tar.gz
rm -f /tmp/deployment-force.tar.gz

# Run force deployment
echo "Running force deployment..."
./force-deploy.sh

echo ""
echo "✅ EC2 deployment complete!"
ENDSSH

echo ""
echo "🎉 Force rebuild deployment finished!"
echo "Your changes should now be live on EC2"

# Cleanup
rm -rf deployment-force deployment-force.tar.gz