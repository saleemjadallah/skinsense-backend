# SkinSense Backend Deployment System

## Overview
This is a clean, unified zero-downtime blue-green deployment system for the SkinSense backend API.

## Architecture
- **Blue-Green Deployment**: Two identical backend containers (blue/green) alternate during deployments
- **Nginx Load Balancer**: Routes traffic to the active container
- **Redis Cache**: Shared between both backends
- **Health Checks**: Ensures new container is healthy before switching
- **Automatic Cleanup**: Removes old containers and unused resources

## Files Structure
```
backend/
├── .github/workflows/
│   └── deploy.yml              # GitHub Actions workflow
├── nginx/
│   ├── nginx.conf             # Main nginx configuration
│   └── conf.d/
│       ├── default.conf       # Server configuration
│       └── active.conf        # Active backend (managed by script)
├── docker-compose.production.yml  # Production Docker configuration
├── deploy.sh                   # Main deployment script
├── cleanup.sh                  # Emergency cleanup script
├── status.sh                   # Status check script
└── Dockerfile                  # Application container
```

## Deployment Process

### Automatic (via GitHub)
```bash
# Simply push to main branch
git push origin main

# GitHub Actions will automatically:
# 1. Build and test the code
# 2. Create deployment package
# 3. Deploy to EC2 with zero downtime
# 4. Run health checks
```

### Manual (on server)
```bash
# Navigate to project directory
cd ~/skinsense-backend

# Run deployment
./deploy.sh

# Check status
./status.sh
```

## Commands

### Deploy
```bash
./deploy.sh
```
- Automatically detects current active backend
- Builds and starts the inactive backend
- Waits for health checks
- Switches nginx traffic
- Stops old container
- Cleans up resources

### Check Status
```bash
./status.sh
```
Shows:
- Active backend (blue/green)
- Container status
- Health check results
- Network status

### Emergency Cleanup
```bash
./cleanup.sh
```
**WARNING**: This will stop and remove all containers!
Use only when deployment is completely broken.

## Container Names
- `skinsense_nginx` - Nginx load balancer
- `skinsense_backend_blue` - Blue backend
- `skinsense_backend_green` - Green backend
- `skinsense_redis` - Redis cache

## Network
All containers use the `skinsense_network` bridge network with subnet `172.20.0.0/16`.

## Health Checks
- **Backend**: `GET /health` returns 200 OK
- **Nginx**: `GET /nginx-status` returns 200 OK
- **Via Proxy**: `GET /health` through nginx

## Troubleshooting

### Deployment Fails
1. Check status: `./status.sh`
2. View logs: `docker logs skinsense_backend_blue` (or green)
3. Check nginx: `docker logs skinsense_nginx`
4. If completely broken: `./cleanup.sh` then `./deploy.sh`

### 502 Bad Gateway
- Backend is not healthy or not running
- Check: `docker ps | grep skinsense`
- Check logs: `docker logs skinsense_backend_[color]`

### Network Issues
- Ensure network exists: `docker network ls | grep skinsense`
- Recreate if needed: `docker network create --driver bridge --subnet 172.20.0.0/16 skinsense_network`

### Container Won't Start
- Check .env file exists
- Check Docker disk space: `df -h`
- Check Docker status: `systemctl status docker`

## Environment Variables
All secrets are stored in GitHub Secrets and injected during deployment:
- `MONGODB_URL`
- `SECRET_KEY`
- `ORBO_AI_API_KEY`
- `ORBO_CLIENT_ID`
- `OPENAI_API_KEY`
- `PERPLEXITY_API_KEY`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `CLOUDFRONT_DOMAIN`
- `ZEPTOMAIL_SEND_TOKEN`

## Rollback
The deployment automatically keeps the previous container until the new one is healthy.
If deployment fails, the old container continues running.

To manually rollback:
1. Identify current active: `cat nginx/conf.d/.active`
2. Switch to other color: `./deploy.sh`

## Monitoring
- Health endpoint: `http://your-server/health`
- Nginx status: `http://your-server/nginx-status`
- Container logs: `docker logs -f skinsense_backend_[color]`

## Security Notes
- Never commit `.env` files
- All secrets in GitHub Secrets
- Containers run with minimal privileges
- Network isolated from host
- No unnecessary ports exposed

## Support
For issues, check:
1. `./status.sh` - Current state
2. Docker logs for specific containers
3. GitHub Actions logs for deployment issues