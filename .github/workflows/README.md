# CI/CD Pipeline Documentation

## Overview
This repository uses GitHub Actions for continuous integration and deployment to AWS EC2.

## Workflows

### 1. CI - Test and Lint (`ci.yml`)
**Triggers:** Push to main/develop, Pull requests to main
**Purpose:** Run tests, linting, and code quality checks
**Steps:**
- Sets up Python environment
- Installs dependencies
- Runs flake8 linting
- Checks code formatting with black
- Runs pytest with coverage
- Uploads coverage reports to Codecov

### 2. Deploy to EC2 (`deploy.yml`)
**Triggers:** Push to main branch, Manual workflow dispatch
**Purpose:** Deploy application to EC2 instance
**Steps:**
- Creates deployment package
- Configures AWS credentials
- Copies files to EC2 via SSH
- Builds and runs Docker containers
- Performs health checks

### 3. Docker Build and Push (`docker.yml`)
**Triggers:** Push to main, Version tags (v*), Manual dispatch
**Purpose:** Build and push Docker images to Docker Hub
**Steps:**
- Builds multi-platform Docker images
- Pushes to Docker Hub registry
- Updates EC2 deployment with latest image

## Required GitHub Secrets

### Essential Secrets
- `MONGODB_URL` - MongoDB connection string
- `SECRET_KEY` - JWT secret key
- `ORBO_AI_API_KEY` - ORBO AI API key
- `ORBO_CLIENT_ID` - ORBO client ID
- `OPENAI_API_KEY` - OpenAI API key
- `PERPLEXITY_API_KEY` - Perplexity API key

### AWS Secrets
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_REGION` - AWS region
- `S3_BUCKET_NAME` - S3 bucket name
- `CLOUDFRONT_DOMAIN` - CloudFront domain

### Deployment Secrets
- `EC2_HOST` - EC2 instance IP/domain
- `EC2_USER` - EC2 username (usually 'ubuntu')
- `EC2_KEY` - Base64 encoded EC2 private key

### Docker Hub Secrets (Optional)
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_PASSWORD` - Docker Hub password/token

### Other Services
- `ZEPTOMAIL_SEND_TOKEN` - Email service token
- `FIREBASE_PROJECT_ID` - Firebase project ID
- `FIREBASE_SERVICE_ACCOUNT` - Base64 encoded Firebase credentials

## Manual Deployment

To trigger a manual deployment:
1. Go to Actions tab
2. Select "Deploy to EC2" workflow
3. Click "Run workflow"
4. Select branch and click "Run workflow"

## Monitoring Deployments

Check deployment status:
- Actions tab shows workflow runs
- Green checkmark = successful deployment
- Red X = failed deployment
- Click on workflow run for detailed logs

## Rollback Procedure

If deployment fails:
1. SSH into EC2 instance
2. Navigate to backup: `cd ~/skinsense-backend.backup.<timestamp>`
3. Restore: `docker-compose up -d`

## Local Testing

Test workflows locally using [act](https://github.com/nektos/act):
```bash
act -j test  # Run CI tests
act -j deploy --secret-file .secrets  # Test deployment
```

## Troubleshooting

### Common Issues
1. **EC2 connection failed**: Check EC2_KEY secret is properly base64 encoded
2. **Docker push failed**: Verify Docker Hub credentials
3. **Health check failed**: Check application logs on EC2
4. **MongoDB connection failed**: Verify MONGODB_URL secret

### Debug Commands
```bash
# Check EC2 logs
ssh ubuntu@<EC2_IP> "cd ~/skinsense-backend && docker-compose logs"

# Check container status
ssh ubuntu@<EC2_IP> "docker ps -a"

# Manual health check
curl http://<EC2_IP>:8000/health
```