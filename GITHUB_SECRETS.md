# GitHub Secrets Required for CI/CD

To set up CI/CD for your SkinSense backend repository, you need to add the following secrets to your GitHub repository settings under Settings → Secrets and variables → Actions.

## Required Secrets

### 1. Database & Cache
- **MONGODB_URL**: Your MongoDB Atlas connection string
  - Example: `mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority`
- **REDIS_URL**: Redis connection URL
  - Example: `redis://redis:6379`

### 2. Security & Authentication
- **SECRET_KEY**: JWT secret key (generate with `openssl rand -hex 32`)
  - Example: `106657caa6c41f4a36c1e691b9a711eec5826e04d8a78f8cb19066fa948a193d`

### 3. AI Services
- **ORBO_AI_API_KEY**: ORBO AI API key for skin analysis
- **ORBO_CLIENT_ID**: ORBO client ID
- **OPENAI_API_KEY**: OpenAI API key for GPT-4
- **PERPLEXITY_API_KEY**: Perplexity API key for product recommendations

### 4. AWS Services
- **AWS_ACCESS_KEY_ID**: AWS access key for S3 and CloudFront
- **AWS_SECRET_ACCESS_KEY**: AWS secret key
- **AWS_REGION**: AWS region (e.g., `eu-north-1`)
- **S3_BUCKET_NAME**: S3 bucket name for image storage
- **CLOUDFRONT_DOMAIN**: CloudFront distribution domain

### 5. Email Service (ZeptoMail)
- **ZEPTOMAIL_SEND_TOKEN**: ZeptoMail API token for sending emails

### 6. Firebase (Push Notifications)
- **FIREBASE_PROJECT_ID**: Firebase project ID
- **FIREBASE_SERVICE_ACCOUNT**: Base64 encoded Firebase service account JSON
  - Encode with: `base64 -i firebase-service-account.json`

### 7. EC2 Deployment
- **EC2_HOST**: Your EC2 instance public IP or domain
  - Example: `56.228.12.81`
- **EC2_USER**: EC2 instance username (usually `ubuntu`)
- **EC2_KEY**: Base64 encoded EC2 private key (.pem file)
  - Encode with: `base64 -i your-ec2-key.pem`

### 8. Docker Registry (Optional)
- **DOCKER_USERNAME**: Docker Hub username
- **DOCKER_PASSWORD**: Docker Hub password or access token

## How to Add Secrets

1. Go to your GitHub repository
2. Click on "Settings" tab
3. Navigate to "Secrets and variables" → "Actions"
4. Click "New repository secret"
5. Add each secret with the exact name listed above
6. Paste the value (make sure no extra spaces or newlines)
7. Click "Add secret"

## Base64 Encoding Instructions

For files that need to be base64 encoded:

### Firebase Service Account:
```bash
# On macOS/Linux:
base64 -i firebase-service-account.json | pbcopy

# On Windows (PowerShell):
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("firebase-service-account.json")) | Set-Clipboard
```

### EC2 Private Key:
```bash
# On macOS/Linux:
base64 -i your-ec2-key.pem | pbcopy

# On Windows (PowerShell):
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("your-ec2-key.pem")) | Set-Clipboard
```

## Security Notes

1. **Never commit secrets to the repository**
2. **Rotate secrets regularly**
3. **Use least privilege principle for AWS IAM**
4. **Enable GitHub secret scanning**
5. **Restrict access to production secrets**
6. **Use different secrets for staging/production**

## Environment-Specific Secrets (Optional)

If you have multiple environments, prefix secrets with environment name:
- `PROD_MONGODB_URL`
- `STAGING_MONGODB_URL`
- `DEV_MONGODB_URL`

## Verification

After adding all secrets, you can verify they're set correctly by:
1. Running the CI/CD workflow manually
2. Checking the Actions tab for any secret-related errors
3. Using the workflow dispatch feature to test deployment