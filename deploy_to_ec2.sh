#!/bin/bash

# Deployment script for SkinSense AI Backend to EC2

EC2_HOST="${EC2_HOST:-56.228.12.81}"
EC2_USER="${EC2_USER:-ubuntu}"
PEM_FILE="${EC2_KEY_PATH:-/Users/saleemjadallah/Desktop/SkinSense(Dev)/skinsense.pem}"
REMOTE_DIR="/home/ubuntu/skinsense-backend"

echo "🚀 Starting deployment to EC2..."

# Create a temporary directory for deployment files
TEMP_DIR=$(mktemp -d)
echo "📁 Created temporary directory: $TEMP_DIR"

# Copy necessary files to temp directory
echo "📋 Copying files..."
mkdir -p "$TEMP_DIR/app"
cp -r app/* "$TEMP_DIR/app/"
cp requirements.txt "$TEMP_DIR/"
cp Dockerfile "$TEMP_DIR/"
cp docker-compose.prod.yml "$TEMP_DIR/docker-compose.yml"
mkdir -p "$TEMP_DIR/scripts"
cp -r scripts/* "$TEMP_DIR/scripts/"
cp create_collections.py "$TEMP_DIR/"

# Create .env file from template if it doesn't exist
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cat > "$TEMP_DIR/.env" << 'EOF'
# MongoDB Configuration
MONGODB_URL=mongodb://mongodb:27017/skinsense
DATABASE_NAME=skinsense

# Redis Configuration
REDIS_URL=redis://redis:6379

# JWT Configuration
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# API Keys (Add your actual keys)
ORBO_API_KEY=your-orbo-api-key
HAUT_AI_API_KEY=your-haut-ai-api-key
OPENAI_API_KEY=your-openai-api-key
PERPLEXITY_API_KEY=your-perplexity-api-key

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=us-east-1
S3_BUCKET_NAME=skinsense-images

# Email Service (Zeptomail)
ZEPTOMAIL_API_KEY=your-zeptomail-api-key
ZEPTOMAIL_FROM_EMAIL=noreply@skinsense.ai
ZEPTOMAIL_FROM_NAME=SkinSense AI

# Firebase Configuration
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY_ID=your-firebase-private-key-id
FIREBASE_PRIVATE_KEY=your-firebase-private-key
FIREBASE_CLIENT_EMAIL=your-firebase-client-email
FIREBASE_CLIENT_ID=your-firebase-client-id

# Environment
ENVIRONMENT=production
DEBUG=false

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://51.20.121.67:8000
EOF
else
    cp .env "$TEMP_DIR/"
fi

# Compress the files
echo "📦 Creating deployment archive..."
cd "$TEMP_DIR"
tar -czf deployment.tar.gz *

# Upload to EC2
echo "📤 Uploading to EC2..."
scp -i "$PEM_FILE" deployment.tar.gz "$EC2_USER@$EC2_HOST:~/"

# Deploy on EC2
echo "🔧 Deploying on EC2..."
ssh -i "$PEM_FILE" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
    # Extract files
    cd ~/skinsense-backend
    tar -xzf ~/deployment.tar.gz
    rm ~/deployment.tar.gz
    
    # Stop existing containers
    echo "🛑 Stopping existing containers..."
    docker network rm skinsense-backend_app_network || true
    docker-compose down || true
    
    # Build and start containers
    echo "🏗️ Building Docker images..."
    docker-compose build --no-cache
    
    echo "🚀 Starting containers..."
    docker-compose up -d
    
    # Wait for services to start
    echo "⏳ Waiting for services to start..."
    sleep 10
    
    # Initialize database collections
    echo "🗄️ Initializing database collections..."
    docker exec -it $(docker ps -q -f name=api) python create_collections.py || true
    docker exec -it $(docker ps -q -f name=api) python scripts/init_collections.py || true
    docker exec -it $(docker ps -q -f name=api) python scripts/init_routine_templates.py || true
    docker exec -it $(docker ps -q -f name=api) python scripts/init_goal_templates.py || true
    
    # Show container status
    echo "📊 Container status:"
    docker-compose ps
    
    echo "✅ Deployment complete!"
ENDSSH

# Cleanup
rm -rf "$TEMP_DIR"

echo "🎉 Deployment finished! API should be available at http://$EC2_HOST:8000"
echo "📚 Documentation available at http://$EC2_HOST:8000/docs"