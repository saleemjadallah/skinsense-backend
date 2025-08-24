# Production Monitoring Setup for api.skinsense.app

## Prerequisites
- SSH access to your EC2 instance
- Docker and Docker Compose installed
- Nginx configured as reverse proxy
- Admin user account in your FastAPI app

## Step 1: Deploy to EC2

1. **Upload monitoring files to your EC2 instance:**
   ```bash
   # From your local machine
   scp -r monitoring/ ubuntu@your-ec2-ip:/opt/skinsense/
   scp docker-compose.monitoring.prod.yml ubuntu@your-ec2-ip:/opt/skinsense/
   scp deploy-monitoring.sh ubuntu@your-ec2-ip:/opt/skinsense/
   ```

2. **SSH into your EC2 instance:**
   ```bash
   ssh ubuntu@your-ec2-ip
   cd /opt/skinsense
   ```

3. **Set environment variables:**
   ```bash
   export GRAFANA_ADMIN_PASSWORD="your-secure-password"
   ```

4. **Run deployment script:**
   ```bash
   ./deploy-monitoring.sh
   ```

## Step 2: Configure Nginx

Add this to your existing Nginx configuration for api.skinsense.app:

```nginx
server {
    server_name api.skinsense.app;
    
    # Your existing FastAPI proxy config...
    
    # Add monitoring proxy
    location /monitoring/ {
        proxy_pass http://127.0.0.1:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        # Security headers
        proxy_hide_header X-Frame-Options;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header Content-Security-Policy "frame-ancestors 'self' https://api.skinsense.app" always;
    }
}
```

## Step 3: Update Production Environment

1. **Update your production .env file:**
   ```bash
   PROMETHEUS_URL="http://prometheus:9090"
   GRAFANA_URL="https://api.skinsense.app"
   ```

2. **Restart your FastAPI application:**
   ```bash
   docker-compose restart app
   # or
   pm2 restart skinsense-api
   ```

## Step 4: Access the Dashboard

1. **Navigate to:** https://api.skinsense.app/api/v1/monitoring/dashboard
2. **Login with your admin credentials**
3. **View real-time metrics and dashboards**

## Security Considerations

1. **Admin-Only Access**: The dashboard requires admin authentication
2. **HTTPS Only**: Ensure all traffic is encrypted
3. **Firewall Rules**: Prometheus and Grafana ports should not be publicly accessible
4. **Strong Passwords**: Use secure passwords for Grafana admin
5. **IP Whitelisting**: Consider restricting access by IP for extra security

## Troubleshooting

### Dashboard not loading?
1. Check Docker containers: `docker ps`
2. View logs: `docker logs skinsense_grafana`
3. Verify Nginx config: `nginx -t`
4. Check browser console for errors

### Metrics not showing?
1. Verify Prometheus is scraping: http://localhost:9090/targets
2. Check FastAPI metrics endpoint: https://api.skinsense.app/metrics
3. Review Prometheus logs: `docker logs skinsense_prometheus`

### Permission denied?
1. Ensure you're logged in as admin
2. Check JWT token expiration
3. Verify admin role in database

## Monitoring URLs on Production

- **Dashboard**: https://api.skinsense.app/api/v1/monitoring/dashboard
- **Health Check**: https://api.skinsense.app/api/v1/monitoring/health/detailed
- **Metrics API**: https://api.skinsense.app/api/v1/monitoring/metrics/active-users

## Backup and Maintenance

1. **Backup Grafana dashboards:**
   ```bash
   docker exec skinsense_grafana grafana-cli admin export-dashboard
   ```

2. **Backup Prometheus data:**
   ```bash
   docker run --rm -v prometheus_data:/data -v $(pwd):/backup busybox tar czf /backup/prometheus-backup.tar.gz /data
   ```

3. **Update containers:**
   ```bash
   docker-compose -f docker-compose.monitoring.prod.yml pull
   docker-compose -f docker-compose.monitoring.prod.yml up -d
   ```

## Cost Optimization

- Prometheus retention: Set to 30 days to limit storage
- Grafana refresh: 5s interval (adjust if needed)
- Consider using AWS CloudWatch for long-term storage
- Monitor data transfer costs