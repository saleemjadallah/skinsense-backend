# GitHub Secrets Setup Guide for SkinSense Backend

## SSH Authentication Fix

The SSH authentication error you're seeing is because the EC2_KEY secret needs to be properly formatted. Here's how to fix it:

### 1. Prepare Your EC2 Private Key

First, you need to get your EC2 private key (the .pem file) in the correct format:

```bash
# On your local machine where you have the skinsense.pem file
cat ~/path/to/skinsense.pem
```

Copy the ENTIRE output, including:
- `-----BEGIN RSA PRIVATE KEY-----` or `-----BEGIN OPENSSH PRIVATE KEY-----`
- All the key content
- `-----END RSA PRIVATE KEY-----` or `-----END OPENSSH PRIVATE KEY-----`

### 2. Add the EC2_KEY Secret to GitHub

1. Go to https://github.com/saleemjadallah/skinsense-backend/settings/secrets/actions
2. Click "New repository secret"
3. Name: `EC2_KEY`
4. Value: Paste the ENTIRE private key content (including BEGIN and END lines)
5. Click "Add secret"

### 3. Verify Other Required Secrets

Make sure these secrets are also set:

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `EC2_HOST` | Your EC2 instance public IP | `54.123.45.67` |
| `EC2_USER` | SSH username (usually ubuntu) | `ubuntu` |
| `MONGODB_URL` | MongoDB connection string | `mongodb+srv://...` |
| `SECRET_KEY` | JWT secret key | `your-secret-key-here` |
| `ORBO_AI_API_KEY` | ORBO API key | `your-orbo-key` |
| `ORBO_CLIENT_ID` | ORBO client ID | `your-orbo-client-id` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `PERPLEXITY_API_KEY` | Perplexity API key | `pplx-...` |
| `AWS_ACCESS_KEY_ID` | AWS access key | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | `your-aws-secret` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `S3_BUCKET_NAME` | S3 bucket name | `skinsense-images` |
| `CLOUDFRONT_DOMAIN` | CloudFront domain | `d12345.cloudfront.net` |
| `ZEPTOMAIL_SEND_TOKEN` | ZeptoMail token | `your-zepto-token` |
| `FIREBASE_PROJECT_ID` | Firebase project | `skinsense-ai` |
| `FIREBASE_SERVICE_ACCOUNT` | Firebase service account JSON | `{...}` (optional) |

### 4. Alternative: Use GitHub's Official Deploy Key Method

If the above doesn't work, you can use GitHub's deploy key approach:

1. Generate a new SSH key pair on your local machine:
```bash
ssh-keygen -t ed25519 -C "github-actions@skinsense" -f deploy_key
```

2. Add the public key to your EC2 instance:
```bash
# SSH into your EC2 instance
ssh -i skinsense.pem ubuntu@your-ec2-ip

# Add the public key to authorized_keys
echo "YOUR_PUBLIC_KEY_CONTENT" >> ~/.ssh/authorized_keys
```

3. Add the private key to GitHub secrets as `EC2_KEY`

### 5. Manual Deployment Alternative

If GitHub Actions continues to fail, you can deploy manually:

```bash
# SSH into your EC2 instance
ssh -i skinsense.pem ubuntu@your-ec2-ip

# Navigate to backend
cd /home/ubuntu/skinsense-backend

# Pull latest changes
git pull origin main

# Run deployment
./deploy-zero-downtime.sh
```

### 6. Test the Deployment

After setting up the secrets correctly:

1. Go to https://github.com/saleemjadallah/skinsense-backend/actions
2. Click on "Simple Deployment" workflow
3. Click "Run workflow" > "Run workflow"
4. Monitor the logs

### Troubleshooting

If you still get authentication errors:

1. **Check key format**: Make sure the key includes all lines (BEGIN, content, END)
2. **Check line endings**: The key should have Unix line endings (LF, not CRLF)
3. **Check permissions**: The EC2 instance's ~/.ssh/authorized_keys should have permission 600
4. **Check username**: Ensure EC2_USER is set to `ubuntu` (or appropriate username)
5. **Check IP**: Ensure EC2_HOST is the current public IP of your instance

### Security Notes

- Never commit the .pem file or .env file to the repository
- Rotate your secrets regularly
- Use GitHub's environment protection rules for production deployments
- Consider using AWS Systems Manager or AWS Secrets Manager for additional security