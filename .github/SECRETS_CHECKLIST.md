# GitHub Secrets Verification Checklist

Use this checklist to verify all required secrets are properly configured in your GitHub repository settings.

## 📍 How to Access GitHub Secrets
1. Go to your GitHub repository
2. Click **Settings** tab
3. Navigate to **Secrets and variables** → **Actions**
4. Verify each secret below exists and has a value

## ✅ Required Secrets Checklist

### 🔑 Authentication & Security
- [ ] **SECRET_KEY** - JWT secret key (generate with `openssl rand -hex 32`)
- [ ] **MONGODB_URL** - MongoDB connection string

### 🤖 AI Services
- [ ] **ORBO_AI_API_KEY** - ORBO AI API key for skin analysis
- [ ] **ORBO_CLIENT_ID** - ORBO client ID
- [ ] **OPENAI_API_KEY** - OpenAI API key for GPT-4
- [ ] **PERPLEXITY_API_KEY** - Perplexity API key (optional)

### ☁️ AWS Services
- [ ] **AWS_ACCESS_KEY_ID** - AWS access key for S3
- [ ] **AWS_SECRET_ACCESS_KEY** - AWS secret key
- [ ] **AWS_REGION** - AWS region (e.g., `eu-north-1`)
- [ ] **S3_BUCKET_NAME** - S3 bucket name for image storage
- [ ] **CLOUDFRONT_DOMAIN** - CloudFront distribution domain

### 🚀 EC2 Deployment (Critical for deployment)
- [ ] **EC2_HOST** - Your EC2 instance public IP (e.g., `56.228.12.81`)
- [ ] **EC2_USER** - EC2 username (usually `ubuntu`)
- [ ] **EC2_KEY** - Base64 encoded EC2 private key (.pem file)

### 📧 Email Service (Optional)
- [ ] **ZEPTOMAIL_SEND_TOKEN** - ZeptoMail API token

### 🌐 CORS & Security (Optional)
- [ ] **BACKEND_CORS_ORIGINS** - Allowed CORS origins
- [ ] **ALLOWED_HOSTS** - Allowed hosts for the backend

## 🔧 Common Issues & Solutions

### ❌ "Invalid EC2 private key format"
**Problem:** EC2_KEY secret is not properly base64 encoded
**Solution:**
```bash
# Encode your .pem file properly:
base64 -i your-ec2-key.pem | pbcopy  # macOS
base64 -w 0 your-ec2-key.pem  # Linux
```

### ❌ "SSH connection failed"
**Possible causes:**
1. Wrong EC2_HOST (check your EC2 public IP)
2. Wrong EC2_USER (should be `ubuntu` for Ubuntu instances)
3. Security group doesn't allow SSH (port 22) from GitHub Actions IPs
4. EC2 instance is stopped or terminated

### ❌ "Missing required secrets"
**Solution:** The workflow will tell you exactly which secrets are missing. Add them one by one.

### ❌ "Health check failed"
**Possible causes:**
1. Application failed to start (check container logs)
2. Wrong security group settings (port 80 not open)
3. Docker containers crashed during deployment

## 🧪 Testing Your Configuration

### Test deployment manually:
1. Go to **Actions** tab in GitHub
2. Click **Deploy to Production** workflow
3. Click **Run workflow**
4. Select branch and click **Run workflow**

### Monitor the deployment:
- Green checkmark = Success ✅
- Red X = Failed ❌ (click for detailed logs)

## 🆘 Getting Help

If deployment continues to fail:
1. Check the **Actions** tab for detailed error logs
2. SSH into your EC2 instance to check container status:
   ```bash
   ssh -i your-key.pem ubuntu@YOUR_EC2_IP
   docker ps -a
   docker logs skinsense_nginx
   ```
3. Verify all secrets are set correctly using this checklist